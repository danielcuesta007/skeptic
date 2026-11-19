import SwiftUI

struct EngineOption: Decodable, Identifiable, Hashable {
    var id: String
    var label: String
}

struct HandoffPayload: Decodable {
    var kind: String
    var provider: String?
    var conversation: String?
    var lastRequest: String?
    var folder: String?
    var digest: String?
    var tty: String?
    var tabTitle: String?
    var usageQuota: String?
    var engines: [EngineOption]?
}

struct HandoffDialogView: View {
    let payload: HandoffPayload
    let onDone: (Bool, String?) -> Void
    @State private var selectedEngineId: String?
    @State private var actionsEnabled = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            header
            if payload.kind == "existing" {
                existingBody
            } else if payload.kind == "close_source" {
                closeSourceBody
            } else if payload.kind == "active_session" {
                activeSessionBody
            } else if payload.kind == "engine_picker" {
                enginePickerBody
            } else if payload.kind == "error" {
                errorBody
            } else {
                confirmBody
            }
            actionRow
            footer
        }
        .onAppear {
            if selectedEngineId == nil {
                selectedEngineId = payload.engines?.first?.id
            }
            if payload.kind == "error" {
                actionsEnabled = true
            } else {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.45) {
                    actionsEnabled = true
                }
            }
        }
        .padding(.horizontal, 24)
        .padding(.vertical, 26)
        .frame(width: sheetWidth)
        .background(SkepticBrand.paper)
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(SkepticBrand.ink.opacity(0.1), lineWidth: 1)
        )
    }

    private var sheetWidth: CGFloat {
        payload.kind == "engine_picker" ? 372 : 388
    }

    private var header: some View {
        HStack(alignment: .top, spacing: 14) {
            HoodHalftoneView(size: 52)
            VStack(alignment: .leading, spacing: 4) {
                Text("Skeptic")
                    .font(SkepticBrand.serif)
                    .foregroundStyle(SkepticBrand.ink)
                Text("Your work. Your memory. Any AI.")
                    .font(SkepticBrand.footnote)
                    .foregroundStyle(SkepticBrand.grey)
                Text(headerCaps)
                    .font(SkepticBrand.labelCaps)
                    .tracking(1.2)
                    .foregroundStyle(SkepticBrand.grey)
                    .padding(.top, 2)
            }
            Spacer(minLength: 0)
        }
        .padding(.bottom, 14)
    }

    private var confirmBody: some View {
        VStack(alignment: .leading, spacing: 12) {
            Divider().overlay(SkepticBrand.graphite.opacity(0.25))
            row("Hand off to", payload.provider ?? "—")
            row("Conversation", payload.conversation ?? "Untitled")
            if let last = payload.lastRequest, !last.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("LAST REQUEST")
                        .font(SkepticBrand.labelCaps)
                        .foregroundStyle(SkepticBrand.grey)
                    Text(last)
                        .font(SkepticBrand.body)
                        .foregroundStyle(SkepticBrand.ink)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            row("Folder", payload.folder ?? "—")
            Text(
                "Skeptic sends the filtered packet in Terminal to the new engine. "
                    + "Confirm background tools in the original tab are idle. "
                    + "The original Terminal tab stays open."
            )
            .font(SkepticBrand.footnote)
            .foregroundStyle(SkepticBrand.graphite)
            if let digest = payload.digest, !digest.isEmpty {
                Text("Packet SHA-256: \(digest)")
                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                    .foregroundStyle(SkepticBrand.grey)
            }
        }
        .padding(.vertical, 4)
    }

    private var headerCaps: String {
        switch payload.kind {
        case "close_source": return "CLOSE STUCK TAB"
        case "active_session": return "SESSION STILL RUNNING"
        case "engine_picker": return "CHOOSE ENGINE"
        case "error": return "HANDOFF BLOCKED"
        default: return "SESSION HANDOFF"
        }
    }

    private var errorBody: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(payload.conversation ?? "Handoff could not continue.")
                .font(SkepticBrand.body)
                .foregroundStyle(SkepticBrand.ink)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.vertical, 6)
    }

    private var enginePickerBody: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(
                "Quotas reflect what Skeptic sees across your open agents right now — "
                    + "the same live session picture as the Skeptic widget."
            )
            .font(SkepticBrand.footnote)
            .foregroundStyle(SkepticBrand.graphite)
            .fixedSize(horizontal: false, vertical: true)
            VStack(spacing: 8) {
                ForEach(payload.engines ?? []) { engine in
                    engineRow(engine)
                }
            }
        }
        .padding(.vertical, 2)
    }

    private func engineRow(_ engine: EngineOption) -> some View {
        let picked = selectedEngineId == engine.id
        return Button {
            selectedEngineId = engine.id
        } label: {
            HStack(alignment: .center, spacing: 10) {
                Image(systemName: picked ? "largecircle.fill.circle" : "circle")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(picked ? SkepticBrand.ink : SkepticBrand.grey)
                Text(engine.label)
                    .font(SkepticBrand.body)
                    .foregroundStyle(SkepticBrand.ink)
                    .multilineTextAlignment(.leading)
                    .lineLimit(4)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 9)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(picked ? Color.white : SkepticBrand.paper)
                    .overlay(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .stroke(picked ? SkepticBrand.ink : SkepticBrand.graphite.opacity(0.22), lineWidth: picked ? 1.5 : 1)
                    )
            )
        }
        .buttonStyle(.plain)
    }

    private var activeSessionBody: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("This session is still running.")
                .font(SkepticBrand.bodySemibold)
                .foregroundStyle(SkepticBrand.ink)
            Divider().overlay(SkepticBrand.graphite.opacity(0.25))
            row("On this tab", payload.provider ?? "—")
            if let quota = payload.usageQuota, !quota.isEmpty {
                row("Quota", quota)
            }
            if let tty = payload.tty, !tty.isEmpty {
                let label = [tty, payload.tabTitle].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " · ")
                row("Terminal tab", label.isEmpty ? tty : label)
            }
            Text(
                "Switching starts a new engine with a handoff packet. "
                    + "The live CLI in this tab can be closed after the new agent accepts the work."
            )
            .font(SkepticBrand.footnote)
            .foregroundStyle(SkepticBrand.graphite)
            .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.vertical, 4)
    }

    private var closeSourceBody: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("The new engine is running.")
                .font(SkepticBrand.bodySemibold)
                .foregroundStyle(SkepticBrand.ink)
            Divider().overlay(SkepticBrand.graphite.opacity(0.25))
            row("Continuing in", payload.provider ?? "—")
            row("Conversation", payload.conversation ?? "Untitled")
            if let tty = payload.tty, !tty.isEmpty {
                let label = [tty, payload.tabTitle].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " · ")
                row("Stuck tab", label.isEmpty ? tty : label)
            }
            Text(
                "Your recovery packet was delivered. Closing the stuck tab ends that live CLI only; "
                    + "the conversation still exists in the provider's session storage."
            )
            .font(SkepticBrand.footnote)
            .foregroundStyle(SkepticBrand.graphite)
            .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.vertical, 4)
    }

    private var existingBody: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("A handoff is already running in another Terminal tab.")
                .font(SkepticBrand.bodySemibold)
                .foregroundStyle(SkepticBrand.ink)
            Text("Continue there — usually Codex, Cursor or Hermes with your SKEPTIC packet — then close that session before starting a new switch.")
                .font(SkepticBrand.body)
                .foregroundStyle(SkepticBrand.graphite)
                .fixedSize(horizontal: false, vertical: true)
            if payload.kind == "existing", let tty = payload.tty, !tty.isEmpty {
                Text("Tab: \(tty)")
                    .font(SkepticBrand.footnote)
                    .foregroundStyle(SkepticBrand.grey)
            }
        }
        .padding(.vertical, 8)
    }

    private var cancelLabel: String {
        switch payload.kind {
        case "existing": return "Cancel"
        case "close_source": return "Keep tab"
        case "active_session": return "Keep working"
        case "engine_picker": return "Cancel"
        case "error": return "OK"
        default: return "Cancel handoff"
        }
    }

    private var approveLabel: String {
        switch payload.kind {
        case "existing": return "Show window"
        case "close_source": return "Close stuck tab"
        case "active_session": return "Switch agent"
        case "engine_picker": return "Continue"
        case "error": return "OK"
        default: return "Hand off"
        }
    }

    private func row(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(label.uppercased())
                .font(SkepticBrand.labelCaps)
                .foregroundStyle(SkepticBrand.grey)
            Text(value)
                .font(SkepticBrand.bodySemibold)
                .foregroundStyle(SkepticBrand.ink)
                .lineLimit(3)
        }
    }

    private var actionRow: some View {
        HStack(spacing: 10) {
            Spacer(minLength: 0)
            if payload.kind != "error" {
                Button(action: { if actionsEnabled { onDone(false, nil) } }) {
                    Text(cancelLabel)
                        .font(SkepticBrand.bodySemibold)
                        .foregroundStyle(SkepticBrand.ink)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 8)
                        .background(
                            RoundedRectangle(cornerRadius: 8, style: .continuous)
                                .stroke(SkepticBrand.graphite.opacity(0.45), lineWidth: 1)
                        )
                }
                .buttonStyle(.plain)
                .disabled(!actionsEnabled)
            }

            Button {
                guard actionsEnabled else { return }
                let engineId = payload.kind == "engine_picker" ? selectedEngineId : nil
                let approved = payload.kind == "error" || engineId != nil || payload.kind != "engine_picker"
                onDone(approved, engineId)
            } label: {
                Text(approveLabel)
                    .font(SkepticBrand.bodySemibold)
                    .foregroundStyle(Color.white)
                    .padding(.horizontal, 18)
                    .padding(.vertical, 8)
                    .background(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .fill(SkepticBrand.ink)
                    )
            }
            .buttonStyle(.plain)
            .disabled(!actionsEnabled || (payload.kind == "engine_picker" && selectedEngineId == nil))
        }
        .padding(.top, 18)
    }

    private var footer: some View {
        Text("A DC Labs™ product")
            .font(SkepticBrand.footnote)
            .foregroundStyle(SkepticBrand.grey)
            .frame(maxWidth: .infinity, alignment: .center)
            .padding(.top, 14)
    }
}