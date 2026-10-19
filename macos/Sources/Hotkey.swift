import AppKit
import Carbon.HIToolbox

/// Raccourci clavier global (API Carbon) : fonctionne sans aucune autorisation spéciale.
final class GlobalHotKey {
    nonisolated(unsafe) private static var current: GlobalHotKey?

    private var ref: EventHotKeyRef?
    private var handler: EventHandlerRef?
    private let action: () -> Void

    init(action: @escaping () -> Void) {
        self.action = action
        GlobalHotKey.current = self
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        InstallEventHandler(GetApplicationEventTarget(), { _, _, _ in
            GlobalHotKey.current?.action()
            return noErr
        }, 1, &spec, nil, &handler)
    }

    func register(_ shortcut: Shortcut) {
        unregister()
        let id = EventHotKeyID(signature: OSType(0x414B_5050), id: 1)  // « AKPP »
        RegisterEventHotKey(shortcut.keyCode, shortcut.carbonModifiers, id, GetApplicationEventTarget(), 0, &ref)
    }

    func unregister() {
        if let ref { UnregisterEventHotKey(ref) }
        ref = nil
    }

    static func carbonModifiers(_ flags: NSEvent.ModifierFlags) -> UInt32 {
        var m: UInt32 = 0
        if flags.contains(.command) { m |= UInt32(cmdKey) }
        if flags.contains(.shift) { m |= UInt32(shiftKey) }
        if flags.contains(.option) { m |= UInt32(optionKey) }
        if flags.contains(.control) { m |= UInt32(controlKey) }
        return m
    }

    static func label(_ flags: NSEvent.ModifierFlags, key: String) -> String {
        var parts: [String] = []
        if flags.contains(.control) { parts.append("⌃") }
        if flags.contains(.option) { parts.append("⌥") }
        if flags.contains(.shift) { parts.append("⇧") }
        if flags.contains(.command) { parts.append("⌘") }
        parts.append(key)
        return parts.joined(separator: " ")
    }

    static func keyName(_ event: NSEvent) -> String {
        switch Int(event.keyCode) {
        case kVK_Space: return "Espace"
        case kVK_Return: return "Entrée"
        case kVK_Tab: return "Tab"
        default: break
        }
        guard let scalar = event.charactersIgnoringModifiers?.unicodeScalars.first else { return "?" }
        if (0xF704...0xF726).contains(scalar.value) { return "F\(scalar.value - 0xF703)" }
        // ⌥ modifie le caractère (⌥C → ©) : on prend la lettre de la touche sans modificateur
        if let plain = event.characters(byApplyingModifiers: [])?.uppercased(), !plain.isEmpty,
           plain.unicodeScalars.first!.value >= 33 {
            return plain
        }
        return String(scalar).uppercased()
    }
}

/// Fenêtre « Appuie sur le raccourci voulu ».
@MainActor
final class ShortcutRecorder: NSObject, NSWindowDelegate {
    var onSave: ((Shortcut) -> Void)?
    var onClose: (() -> Void)?

    private var window: NSWindow?
    private var monitor: Any?
    private var pending = Shortcut.optionC
    private let display = NSTextField(labelWithString: "")

    func open(current: Shortcut) {
        NSApp.activate(ignoringOtherApps: true)
        if let w = window { w.makeKeyAndOrderFront(nil); return }
        pending = current

        let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 380, height: 200),
                         styleMask: [.titled, .closable], backing: .buffered, defer: false)
        w.title = "Raccourci AikoPipette"
        w.isReleasedWhenClosed = false
        w.delegate = self

        let intro = NSTextField(wrappingLabelWithString:
            "Appuie sur la combinaison qui lancera la pipette (une touche, avec ou sans ⌃ ⌥ ⇧ ⌘).")
        intro.font = .systemFont(ofSize: 13)
        display.font = .systemFont(ofSize: 24, weight: .semibold)
        display.alignment = .center
        display.stringValue = current.label

        let reset = NSButton(title: "Rétablir ⌥ C", target: self, action: #selector(resetDefault))
        let cancel = NSButton(title: "Annuler", target: self, action: #selector(cancelRecording))
        let save = NSButton(title: "Enregistrer", target: self, action: #selector(saveRecording))
        save.bezelColor = Palette.accent
        for b in [reset, cancel, save] { b.refusesFirstResponder = true }
        let spacer = NSView()
        spacer.setContentHuggingPriority(.defaultLow, for: .horizontal)
        let buttons = NSStackView(views: [reset, spacer, cancel, save])

        let stack = NSStackView(views: [intro, display, buttons])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 16
        stack.edgeInsets = NSEdgeInsets(top: 20, left: 20, bottom: 18, right: 20)
        stack.translatesAutoresizingMaskIntoConstraints = false
        let content = NSView()
        content.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: content.leadingAnchor),
            stack.trailingAnchor.constraint(equalTo: content.trailingAnchor),
            stack.topAnchor.constraint(equalTo: content.topAnchor),
            stack.bottomAnchor.constraint(equalTo: content.bottomAnchor),
            intro.widthAnchor.constraint(equalToConstant: 340),
            display.widthAnchor.constraint(equalToConstant: 340),
            buttons.widthAnchor.constraint(equalToConstant: 340),
        ])
        w.contentView = content
        w.center()
        window = w

        monitor = NSEvent.addLocalMonitorForEvents(matching: [.keyDown]) { [weak self] event in
            MainActor.assumeIsolated { self?.handle(event) }
            return nil
        }
        w.makeKeyAndOrderFront(nil)
    }

    private func handle(_ event: NSEvent) {
        if Int(event.keyCode) == kVK_Escape { cancelRecording(); return }
        let flags = event.modifierFlags.intersection([.command, .shift, .option, .control])
        let key = GlobalHotKey.keyName(event)
        pending = Shortcut(keyCode: UInt32(event.keyCode),
                           carbonModifiers: GlobalHotKey.carbonModifiers(flags),
                           label: GlobalHotKey.label(flags, key: key))
        display.stringValue = pending.label
    }

    @objc private func resetDefault() {
        pending = .optionC
        display.stringValue = pending.label
    }

    @objc private func saveRecording() {
        onSave?(pending)
        window?.close()
    }

    @objc private func cancelRecording() { window?.close() }

    func windowWillClose(_ notification: Notification) {
        if let monitor { NSEvent.removeMonitor(monitor) }
        monitor = nil
        window = nil
        onClose?()
    }
}
