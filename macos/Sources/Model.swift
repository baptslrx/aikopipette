import AppKit
import ImageIO
import ServiceManagement

// MARK: - Couleurs

struct RGB: Equatable {
    var r: Int, g: Int, b: Int

    init(r: Int, g: Int, b: Int) {
        self.r = max(0, min(255, r)); self.g = max(0, min(255, g)); self.b = max(0, min(255, b))
    }

    init?(hex: String) {
        var s = hex.trimmingCharacters(in: .whitespaces)
        if s.hasPrefix("#") { s.removeFirst() }
        guard s.count == 6, let v = Int(s, radix: 16) else { return nil }
        self.init(r: (v >> 16) & 0xFF, g: (v >> 8) & 0xFF, b: v & 0xFF)
    }

    init(_ color: NSColor) {
        let c = color.usingColorSpace(.sRGB) ?? color
        self.init(r: Int((c.redComponent * 255).rounded()),
                  g: Int((c.greenComponent * 255).rounded()),
                  b: Int((c.blueComponent * 255).rounded()))
    }

    var hex: String { String(format: "#%02X%02X%02X", r, g, b) }
    var rgbText: String { "rgb(\(r), \(g), \(b))" }

    var hslText: String {
        let rf = Double(r) / 255, gf = Double(g) / 255, bf = Double(b) / 255
        let mx = max(rf, gf, bf), mn = min(rf, gf, bf)
        let l = (mx + mn) / 2
        var h = 0.0, s = 0.0
        if mx != mn {
            let d = mx - mn
            s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn)
            switch mx {
            case rf: h = (gf - bf) / d + (gf < bf ? 6 : 0)
            case gf: h = (bf - rf) / d + 2
            default: h = (rf - gf) / d + 4
            }
            h /= 6
        }
        return "hsl(\(Int((h * 360).rounded())), \(Int((s * 100).rounded()))%, \(Int((l * 100).rounded()))%)"
    }

    var nsColor: NSColor {
        NSColor(srgbRed: CGFloat(r) / 255, green: CGFloat(g) / 255, blue: CGFloat(b) / 255, alpha: 1)
    }

    /// Texte foncé ou clair selon la couleur de fond
    var isLight: Bool { (0.299 * Double(r) + 0.587 * Double(g) + 0.114 * Double(b)) > 160 }
}

enum CopyFormat: String, CaseIterable {
    case hex = "HEX", rgb = "RGB", hsl = "HSL"

    func text(_ c: RGB) -> String {
        switch self {
        case .hex: return c.hex
        case .rgb: return c.rgbText
        case .hsl: return c.hslText
        }
    }
}

// MARK: - Raccourci global (touche + modificateurs, format Carbon)

struct Shortcut: Codable, Equatable {
    var keyCode: UInt32
    var carbonModifiers: UInt32
    var label: String

    static let optionC = Shortcut(keyCode: 8, carbonModifiers: 2048, label: "⌥ C")  // kVK_ANSI_C + optionKey
}

// MARK: - Données de l'appli

@MainActor
final class ColorStore: ObservableObject {
    @Published var history: [String] {
        didSet { UserDefaults.standard.set(history, forKey: "history") }
    }
    @Published var palette: [String] = []
    @Published var paletteSource: String = ""
    @Published var format: CopyFormat {
        didSet { UserDefaults.standard.set(format.rawValue, forKey: "format") }
    }
    @Published var shortcut: Shortcut {
        didSet {
            if let data = try? JSONEncoder().encode(shortcut) {
                UserDefaults.standard.set(data, forKey: "shortcut")
            }
        }
    }
    @Published var launchAtLogin: Bool = SMAppService.mainApp.status == .enabled
    @Published var flash: String?   // couleur qui vient d'être copiée

    init() {
        let d = UserDefaults.standard
        history = d.stringArray(forKey: "history") ?? []
        format = CopyFormat(rawValue: d.string(forKey: "format") ?? "") ?? .hex
        if let data = d.data(forKey: "shortcut"), let s = try? JSONDecoder().decode(Shortcut.self, from: data) {
            shortcut = s
        } else {
            shortcut = .optionC
        }
    }

    @discardableResult
    func add(_ color: RGB) -> String {
        history.removeAll { $0 == color.hex }
        history.insert(color.hex, at: 0)
        if history.count > 32 { history.removeLast(history.count - 32) }
        return copy(color.hex)
    }

    @discardableResult
    func copy(_ hex: String, as fmt: CopyFormat? = nil) -> String {
        guard let c = RGB(hex: hex) else { return hex }
        let text = (fmt ?? format).text(c)
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
        flash = hex
        Task { @MainActor [weak self] in
            try? await Task.sleep(nanoseconds: 1_200_000_000)
            if self?.flash == hex { self?.flash = nil }
        }
        return text
    }

    func copyPalette() {
        let text = palette.compactMap { RGB(hex: $0) }.map { format.text($0) }.joined(separator: "\n")
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
    }

    func remove(_ hex: String) { history.removeAll { $0 == hex } }
    func clearHistory() { history = [] }

    func extractPalette(from url: URL) {
        let name = url.lastPathComponent
        Task.detached(priority: .userInitiated) {
            let colors = PaletteExtractor.extract(from: url, count: 6)
            await MainActor.run {
                self.palette = colors.map(\.hex)
                self.paletteSource = colors.isEmpty ? "Image illisible" : name
            }
        }
    }

    func setLaunchAtLogin(_ on: Bool) {
        do {
            if on { try SMAppService.mainApp.register() } else { try SMAppService.mainApp.unregister() }
        } catch {}
        launchAtLogin = SMAppService.mainApp.status == .enabled
    }
}

// MARK: - Palette principale d'une image (k-moyennes)

enum PaletteExtractor {
    static func extract(from url: URL, count: Int) -> [RGB] {
        guard let src = CGImageSourceCreateWithURL(url as CFURL, nil) else { return [] }
        let opts: [String: Any] = [
            kCGImageSourceCreateThumbnailFromImageAlways as String: true,
            kCGImageSourceCreateThumbnailWithTransform as String: true,
            kCGImageSourceThumbnailMaxPixelSize as String: 96,
        ]
        guard let img = CGImageSourceCreateThumbnailAtIndex(src, 0, opts as CFDictionary) else { return [] }
        let w = img.width, h = img.height
        var data = [UInt8](repeating: 0, count: w * h * 4)
        guard let ctx = CGContext(data: &data, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4,
                                  space: CGColorSpace(name: CGColorSpace.sRGB)!,
                                  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return [] }
        ctx.draw(img, in: CGRect(x: 0, y: 0, width: w, height: h))

        var pixels: [(Double, Double, Double)] = []
        pixels.reserveCapacity(w * h)
        for i in stride(from: 0, to: data.count, by: 4) where data[i + 3] > 200 {
            pixels.append((Double(data[i]), Double(data[i + 1]), Double(data[i + 2])))
        }
        guard !pixels.isEmpty else { return [] }
        return kmeans(pixels, k: count)
    }

    static func kmeans(_ px: [(Double, Double, Double)], k: Int) -> [RGB] {
        func dist(_ a: (Double, Double, Double), _ b: (Double, Double, Double)) -> Double {
            let dr = a.0 - b.0, dg = a.1 - b.1, db = a.2 - b.2
            return dr * dr * 0.3 + dg * dg * 0.59 + db * db * 0.11
        }
        // Départ déterministe : le pixel moyen, puis les plus éloignés (k-means++ sans hasard)
        var centers: [(Double, Double, Double)] = [px[px.count / 2]]
        while centers.count < min(k * 2, px.count) {
            var best = px[0], bestD = -1.0
            for p in px {
                let d = centers.map { dist(p, $0) }.min() ?? 0
                if d > bestD { bestD = d; best = p }
            }
            if bestD <= 0 { break }
            centers.append(best)
        }
        var counts = [Int](repeating: 0, count: centers.count)
        for _ in 0..<12 {
            var sums = [(Double, Double, Double)](repeating: (0, 0, 0), count: centers.count)
            counts = [Int](repeating: 0, count: centers.count)
            for p in px {
                var bi = 0, bd = Double.greatestFiniteMagnitude
                for (i, c) in centers.enumerated() {
                    let d = dist(p, c)
                    if d < bd { bd = d; bi = i }
                }
                sums[bi].0 += p.0; sums[bi].1 += p.1; sums[bi].2 += p.2
                counts[bi] += 1
            }
            for i in centers.indices where counts[i] > 0 {
                let n = Double(counts[i])
                centers[i] = (sums[i].0 / n, sums[i].1 / n, sums[i].2 / n)
            }
        }
        // Les plus présentes d'abord, sans doublons visuels
        let order = centers.indices.filter { counts[$0] > 0 }.sorted { counts[$0] > counts[$1] }
        var result: [(Double, Double, Double)] = []
        for i in order where result.allSatisfy({ dist($0, centers[i]) > 600 }) {
            result.append(centers[i])
            if result.count == k { break }
        }
        return result.map { RGB(r: Int($0.0.rounded()), g: Int($0.1.rounded()), b: Int($0.2.rounded())) }
    }
}
