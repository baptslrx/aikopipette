import AppKit
import SwiftUI

@main
@MainActor
struct AikoPipetteMain {
    static func main() {
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.setActivationPolicy(.accessory)
        app.run()
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var store: ColorStore!
    private var statusItem: NSStatusItem!
    private var popover: NSPopover!
    private var hotkey: GlobalHotKey!
    private var recorder: ShortcutRecorder!
    private var sampler: NSColorSampler?
    private var bubble: ColorBubble!

    func applicationDidFinishLaunching(_ notification: Notification) {
        store = ColorStore()
        bubble = ColorBubble()

        hotkey = GlobalHotKey { [weak self] in
            MainActor.assumeIsolated { self?.pick() }
        }
        hotkey.register(store.shortcut)

        recorder = ShortcutRecorder()
        recorder.onSave = { [weak self] shortcut in
            self?.store.shortcut = shortcut
        }
        recorder.onClose = { [weak self] in
            guard let self else { return }
            self.hotkey.register(self.store.shortcut)
        }

        popover = NSPopover()
        popover.behavior = .transient
        popover.animates = true
        popover.contentViewController = NSHostingController(rootView: PaletteView(
            store: store,
            onPick: { [weak self] in self?.pick() },
            onShortcut: { [weak self] in self?.changeShortcut() },
            onQuit: { NSApp.terminate(nil) }))

        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        statusItem.button?.image = pipetteIcon()
        statusItem.button?.toolTip = "AikoPipette"
        statusItem.button?.target = self
        statusItem.button?.action = #selector(togglePopover)

        if !UserDefaults.standard.bool(forKey: "welcomed") {
            UserDefaults.standard.set(true, forKey: "welcomed")
            showWelcome()
        }
    }

    @objc private func togglePopover() {
        guard let button = statusItem.button else { return }
        if popover.isShown {
            popover.performClose(nil)
        } else {
            NSApp.activate(ignoringOtherApps: true)
            popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
        }
    }

    /// Lance la loupe système de macOS : clic = couleur prise et copiée, Échap = annuler.
    private func pick() {
        popover.performClose(nil)
        let s = NSColorSampler()
        sampler = s
        s.show { [weak self] color in
            MainActor.assumeIsolated {
                guard let self else { return }
                self.sampler = nil
                guard let color else { return }
                let rgb = RGB(color)
                let text = self.store.add(rgb)
                self.bubble.show(rgb, text: text, near: NSEvent.mouseLocation)
            }
        }
    }

    private func changeShortcut() {
        popover.performClose(nil)
        hotkey.unregister()   // pour pouvoir enregistrer le raccourci actuel lui-même
        recorder.open(current: store.shortcut)
    }

    private func showWelcome() {
        NSApp.activate(ignoringOtherApps: true)
        let alert = NSAlert()
        alert.messageText = "AikoPipette est prête"
        alert.informativeText = """
        Appuie sur \(store.shortcut.label) n'importe où : une loupe apparaît. Clique sur une couleur, elle est copiée (HEX par défaut) et ajoutée à ton historique.

        Clique sur l'icône pipette dans la barre des menus pour retrouver l'historique, changer le format (HEX, RGB, HSL) ou glisser une image et obtenir sa palette.
        """
        alert.addButton(withTitle: "C'est parti")
        alert.runModal()
    }
}

/// Icône de la barre des menus : une pipette (symbole système), en image modèle.
@MainActor
func pipetteIcon() -> NSImage {
    let config = NSImage.SymbolConfiguration(pointSize: 14, weight: .medium)
    let img = NSImage(systemSymbolName: "eyedropper.halffull", accessibilityDescription: "AikoPipette")?
        .withSymbolConfiguration(config)
        ?? NSImage(systemSymbolName: "eyedropper", accessibilityDescription: "AikoPipette")
        ?? NSImage(size: NSSize(width: 16, height: 16))
    img.isTemplate = true
    return img
}

// MARK: - Bulle « ● #7DC8FF copié »

@MainActor
final class BubbleView: NSView {
    var color = NSColor.white
    var text = ""

    override func viewDidChangeEffectiveAppearance() {
        super.viewDidChangeEffectiveAppearance()
        needsDisplay = true
    }

    override func draw(_ dirtyRect: NSRect) {
        let dark = effectiveAppearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
        let bg = dark ? NSColor(srgbRed: 0.04, green: 0.04, blue: 0.05, alpha: 0.97) : NSColor(white: 1, alpha: 0.98)
        let line = dark ? NSColor(white: 1, alpha: 0.09) : NSColor(white: 0, alpha: 0.08)
        let ink = dark ? NSColor(srgbRed: 0.96, green: 0.97, blue: 0.98, alpha: 1)
                       : NSColor(srgbRed: 0.04, green: 0.05, blue: 0.06, alpha: 1)

        let box = NSBezierPath(roundedRect: bounds.insetBy(dx: 0.5, dy: 0.5), xRadius: bounds.height / 2,
                               yRadius: bounds.height / 2)
        bg.setFill(); box.fill()
        line.setStroke(); box.lineWidth = 1; box.stroke()

        let dot = NSBezierPath(ovalIn: NSRect(x: 10, y: bounds.midY - 9, width: 18, height: 18))
        color.setFill(); dot.fill()
        line.setStroke(); dot.stroke()

        let attrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.monospacedSystemFont(ofSize: 12.5, weight: .semibold),
            .foregroundColor: ink,
        ]
        let s = NSAttributedString(string: text, attributes: attrs)
        s.draw(at: NSPoint(x: 36, y: bounds.midY - s.size().height / 2))
    }
}

@MainActor
final class ColorBubble {
    private let panel: NSPanel
    private let view = BubbleView()
    private var generation = 0

    init() {
        let p = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 200, height: 36),
                        styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        p.isOpaque = false
        p.backgroundColor = .clear
        p.hasShadow = true
        p.level = .popUpMenu
        p.ignoresMouseEvents = true
        p.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]
        p.contentView = view
        panel = p
    }

    func show(_ rgb: RGB, text: String, near point: NSPoint) {
        generation += 1
        let g = generation
        view.color = rgb.nsColor
        view.text = "\(text)  copié"
        let width = NSAttributedString(string: view.text,
                                       attributes: [.font: NSFont.monospacedSystemFont(ofSize: 12.5, weight: .semibold)])
            .size().width + 52
        var frame = NSRect(x: point.x - width / 2, y: point.y + 24, width: width, height: 36)
        if let screen = NSScreen.screens.first(where: { NSMouseInRect(point, $0.frame, false) }) {
            let v = screen.visibleFrame
            frame.origin.x = min(max(frame.origin.x, v.minX + 8), v.maxX - width - 8)
            frame.origin.y = min(frame.origin.y, v.maxY - 44)
        }
        panel.setFrame(frame, display: true)
        view.needsDisplay = true
        panel.invalidateShadow()
        panel.orderFrontRegardless()
        Task { @MainActor [weak self] in
            try? await Task.sleep(nanoseconds: 1_600_000_000)
            guard let self, self.generation == g else { return }
            self.panel.orderOut(nil)
        }
    }
}
