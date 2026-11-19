import AppKit
import SwiftUI

@main
enum Main {
    static func main() {
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.setActivationPolicy(.accessory)
        app.run()
        exit(delegate.exitCode)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    fileprivate var exitCode: Int32 = 2
    private var panel: NSPanel?
    private var engineChoice: String?
    private var keysEnabled = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        guard let payload = Self.loadPayload() else {
            exitCode = 2
            NSApp.terminate(nil)
            return
        }
        let engineCount = payload.engines?.count ?? 0
        let panelWidth: CGFloat = payload.kind == "engine_picker" ? 372 : 388
        let panelHeight: CGFloat = payload.kind == "engine_picker"
            ? max(panelWidth + 80, CGFloat(400 + engineCount * 64))
            : (payload.kind == "confirm" ? 600 : 520)
        let content = HandoffDialogView(
            payload: payload,
            onDone: { [weak self] approved, engineId in
                self?.engineChoice = engineId
                self?.finish(approved: approved, payload: payload)
            }
        )
        let host = NSHostingController(rootView: content)
        let panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: panelWidth, height: min(panelHeight, 620)),
            styleMask: [.nonactivatingPanel, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        panel.title = "Skeptic · Session Handoff"
        panel.titlebarAppearsTransparent = true
        panel.titleVisibility = .hidden
        panel.isMovableByWindowBackground = true
        panel.backgroundColor = SkepticBrand.paperNS
        panel.isOpaque = true
        panel.hasShadow = true
        panel.contentViewController = host
        host.view.wantsLayer = true
        if let layer = host.view.layer {
            layer.cornerRadius = 20
            layer.masksToBounds = true
        }
        if let winLayer = panel.contentView?.layer {
            winLayer.cornerRadius = 20
            winLayer.masksToBounds = true
        }
        panel.isReleasedWhenClosed = false
        panel.level = .modalPanel
        panel.collectionBehavior = [.moveToActiveSpace, .fullScreenAuxiliary]
        panel.standardWindowButton(.closeButton)?.isHidden = true
        panel.standardWindowButton(.miniaturizeButton)?.isHidden = true
        panel.standardWindowButton(.zoomButton)?.isHidden = true
        panel.center()
        self.panel = panel
        panel.makeKeyAndOrderFront(nil)
        panel.orderFrontRegardless()
        NSApp.activate(ignoringOtherApps: true)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.45) { [weak self] in
            self?.keysEnabled = true
        }
        NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            guard let self, self.keysEnabled else { return event }
            if event.keyCode == 53 {
                self.engineChoice = nil
                self.finish(approved: false, payload: payload)
                return nil
            }
            return event
        }
    }

    private func finish(approved: Bool, payload: HandoffPayload) {
        if approved, payload.kind == "existing", let tty = payload.tty {
            Self.focusTerminal(tty: tty)
        }
        if approved, payload.kind == "engine_picker", let id = engineChoice {
            FileHandle.standardOutput.write((id + "\n").data(using: .utf8)!)
            if let path = Self.resultPath() {
                try? id.write(toFile: path, atomically: true, encoding: .utf8)
            }
        } else if let path = Self.resultPath() {
            let marker = approved ? (payload.kind == "confirm" ? "reviewed" : "ok") : "cancel"
            try? marker.write(toFile: path, atomically: true, encoding: .utf8)
        }
        exitCode = approved ? 0 : 1
        panel?.close()
        NSApp.terminate(nil)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    static func loadPayload() -> HandoffPayload? {
        let args = Array(CommandLine.arguments.dropFirst())
        guard let pathIndex = args.firstIndex(of: "--payload"),
              pathIndex + 1 < args.count else { return nil }
        let path = args[pathIndex + 1]
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: path)) else { return nil }
        return try? JSONDecoder().decode(HandoffPayload.self, from: data)
    }

    static func resultPath() -> String? {
        let args = Array(CommandLine.arguments.dropFirst())
        guard let pathIndex = args.firstIndex(of: "--result"),
              pathIndex + 1 < args.count else { return nil }
        return args[pathIndex + 1]
    }

    static func focusTerminal(tty: String) {
        let short = tty.hasPrefix("/dev/") ? String(tty.dropFirst(5)) : tty
        let script = """
        tell application "Terminal"
            repeat with win in windows
                repeat with tabItem in tabs of win
                    if tty of tabItem contains "\(short)" then
                        set selected tab of win to tabItem
                        set index of win to 1
                        activate
                        return
                    end if
                end repeat
            end repeat
        end tell
        """
        var error: NSDictionary?
        if let appleScript = NSAppleScript(source: script) {
            appleScript.executeAndReturnError(&error)
        }
    }
}