import AppKit
import SwiftUI
import UniformTypeIdentifiers

/// Charte AikoRoue / AikoPipette : noir ou blanc + bleu clair.
enum Palette {
    static let accent = NSColor(srgbRed: 0.49, green: 0.78, blue: 1.0, alpha: 1)   // #7DC8FF
    static let accentUI = Color(red: 0.49, green: 0.78, blue: 1.0)
    static let onAccent = Color(red: 0.02, green: 0.07, blue: 0.11)

    static func background(_ s: ColorScheme) -> Color {
        s == .dark ? Color(red: 0.04, green: 0.04, blue: 0.05) : .white
    }
    static func surface(_ s: ColorScheme) -> Color {
        s == .dark ? Color(red: 0.09, green: 0.09, blue: 0.10) : Color(red: 0.95, green: 0.97, blue: 0.99)
    }
    static func line(_ s: ColorScheme) -> Color {
        s == .dark ? Color.white.opacity(0.09) : Color.black.opacity(0.08)
    }
    static func text(_ s: ColorScheme) -> Color {
        s == .dark ? Color(red: 0.96, green: 0.97, blue: 0.98) : Color(red: 0.04, green: 0.05, blue: 0.06)
    }
    static func subtext(_ s: ColorScheme) -> Color {
        s == .dark ? Color(red: 0.55, green: 0.58, blue: 0.62) : Color(red: 0.42, green: 0.45, blue: 0.50)
    }
}

struct PaletteView: View {
    @ObservedObject var store: ColorStore
    var onPick: () -> Void
    var onShortcut: () -> Void
    var onQuit: () -> Void

    @Environment(\.colorScheme) private var scheme
    @State private var dropping = false

    private let columns = Array(repeating: GridItem(.fixed(30), spacing: 8), count: 8)

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            header
            pickButton
            if let hex = store.history.first, let c = RGB(hex: hex) { current(c) }
            section("Historique")
            history
            section("Palette d'une image")
            dropZone
            footer
        }
        .padding(16)
        .frame(width: 320)
        .background(Palette.background(scheme))
    }

    // MARK: Parties

    private var header: some View {
        HStack {
            Text("AikoPipette").font(.system(size: 13, weight: .semibold)).foregroundColor(Palette.text(scheme))
            Spacer()
            Text(store.shortcut.label)
                .font(.system(size: 11, weight: .medium))
                .foregroundColor(Palette.subtext(scheme))
                .padding(.horizontal, 7).padding(.vertical, 3)
                .overlay(RoundedRectangle(cornerRadius: 5).stroke(Palette.line(scheme)))
        }
    }

    private var pickButton: some View {
        Button(action: onPick) {
            HStack(spacing: 8) {
                Image(systemName: "eyedropper")
                Text("Prendre une couleur").fontWeight(.semibold)
            }
            .font(.system(size: 13))
            .foregroundColor(Palette.onAccent)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 9)
            .background(RoundedRectangle(cornerRadius: 8).fill(Palette.accentUI))
        }
        .buttonStyle(.plain)
    }

    private func current(_ c: RGB) -> some View {
        HStack(spacing: 12) {
            RoundedRectangle(cornerRadius: 8)
                .fill(Color(nsColor: c.nsColor))
                .frame(width: 46, height: 46)
                .overlay(RoundedRectangle(cornerRadius: 8).stroke(Palette.line(scheme)))
            VStack(alignment: .leading, spacing: 3) {
                ForEach(CopyFormat.allCases, id: \.self) { fmt in
                    Button { store.copy(c.hex, as: fmt) } label: {
                        Text(fmt.text(c))
                            .font(.system(size: fmt == .hex ? 14 : 11, weight: fmt == .hex ? .semibold : .regular,
                                          design: .monospaced))
                            .foregroundColor(fmt == .hex ? Palette.text(scheme) : Palette.subtext(scheme))
                    }
                    .buttonStyle(.plain)
                    .help("Copier")
                }
            }
            Spacer()
            if store.flash != nil {
                Text("Copié").font(.system(size: 11, weight: .semibold)).foregroundColor(Palette.accentUI)
            }
        }
    }

    private func section(_ title: String) -> some View {
        Text(title.uppercased())
            .font(.system(size: 10, weight: .semibold))
            .tracking(0.6)
            .foregroundColor(Palette.subtext(scheme))
    }

    private var history: some View {
        Group {
            if store.history.isEmpty {
                Text("Les couleurs prises s'afficheront ici.")
                    .font(.system(size: 12)).foregroundColor(Palette.subtext(scheme))
            } else {
                LazyVGrid(columns: columns, alignment: .leading, spacing: 8) {
                    ForEach(store.history, id: \.self) { hex in
                        swatch(hex, size: 30)
                    }
                }
            }
        }
    }

    private func swatch(_ hex: String, size: CGFloat) -> some View {
        let c = RGB(hex: hex) ?? RGB(r: 0, g: 0, b: 0)
        return RoundedRectangle(cornerRadius: 7)
            .fill(Color(nsColor: c.nsColor))
            .frame(width: size, height: size)
            .overlay(RoundedRectangle(cornerRadius: 7)
                .stroke(store.flash == hex ? Palette.accentUI : Palette.line(scheme),
                        lineWidth: store.flash == hex ? 2 : 1))
            .contentShape(Rectangle())
            .onTapGesture { store.copy(hex) }
            .help("\(hex) — clic pour copier")
            .contextMenu {
                ForEach(CopyFormat.allCases, id: \.self) { fmt in
                    Button("Copier \(fmt.text(c))") { store.copy(hex, as: fmt) }
                }
                Divider()
                Button("Supprimer") { store.remove(hex) }
            }
    }

    private var dropZone: some View {
        VStack(alignment: .leading, spacing: 10) {
            if store.palette.isEmpty {
                HStack {
                    Spacer()
                    VStack(spacing: 4) {
                        Image(systemName: "photo").font(.system(size: 16))
                        Text(store.paletteSource.isEmpty ? "Glisse une image ici" : store.paletteSource)
                            .font(.system(size: 12))
                    }
                    .foregroundColor(dropping ? Palette.accentUI : Palette.subtext(scheme))
                    Spacer()
                }
                .padding(.vertical, 18)
            } else {
                HStack(spacing: 6) {
                    ForEach(store.palette, id: \.self) { hex in
                        swatch(hex, size: 36)
                    }
                }
                HStack {
                    Text(store.paletteSource).font(.system(size: 11)).foregroundColor(Palette.subtext(scheme))
                        .lineLimit(1).truncationMode(.middle)
                    Spacer()
                    Button("Tout copier") { store.copyPalette() }
                        .buttonStyle(.plain)
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(Palette.accentUI)
                }
            }
        }
        .padding(10)
        .frame(maxWidth: .infinity)
        .background(RoundedRectangle(cornerRadius: 10).fill(Palette.surface(scheme)))
        .overlay(RoundedRectangle(cornerRadius: 10)
            .stroke(dropping ? Palette.accentUI : Palette.line(scheme),
                    style: StrokeStyle(lineWidth: dropping ? 1.5 : 1, dash: store.palette.isEmpty ? [5, 4] : [])))
        .onDrop(of: [UTType.fileURL], isTargeted: $dropping) { providers in
            guard let provider = providers.first else { return false }
            let store = self.store
            _ = provider.loadObject(ofClass: URL.self) { url, _ in
                guard let url else { return }
                Task { @MainActor in store.extractPalette(from: url) }
            }
            return true
        }
    }

    private var footer: some View {
        HStack {
            Picker("", selection: $store.format) {
                ForEach(CopyFormat.allCases, id: \.self) { Text($0.rawValue).tag($0) }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .frame(width: 150)
            Spacer()
            Menu {
                Button("Changer le raccourci…", action: onShortcut)
                Toggle("Ouvrir au démarrage", isOn: Binding(get: { store.launchAtLogin },
                                                           set: { store.setLaunchAtLogin($0) }))
                Button("Effacer l'historique") { store.clearHistory() }
                Divider()
                Button("Quitter AikoPipette", action: onQuit)
            } label: {
                Image(systemName: "ellipsis.circle").font(.system(size: 15))
            }
            .menuStyle(.borderlessButton)
            .menuIndicator(.hidden)
            .fixedSize()
        }
    }
}
