import AppKit
import SwiftUI

enum SkepticBrand {
    static let ink = Color(red: 0x0B / 255.0, green: 0x0B / 255.0, blue: 0x0C / 255.0)
    static let paper = Color(red: 0xF7 / 255.0, green: 0xF7 / 255.0, blue: 0xF7 / 255.0)
    static let grey = Color(red: 0x8C / 255.0, green: 0x8C / 255.0, blue: 0x8C / 255.0)
    static let graphite = Color(red: 0x3D / 255.0, green: 0x3D / 255.0, blue: 0x3D / 255.0)

    static var serif: Font { .system(size: 28, weight: .medium, design: .serif) }
    static func serifFallback() -> Font { .system(size: 28, weight: .medium, design: .serif) }

    static var labelCaps: Font {
        .system(size: 11, weight: .semibold, design: .monospaced)
    }

    static var body: Font { .system(size: 13, weight: .regular) }
    static var bodySemibold: Font { .system(size: 13, weight: .semibold) }
    static var footnote: Font { .system(size: 11, weight: .medium) }

    static var paperNS: NSColor {
        NSColor(red: 0xF7 / 255.0, green: 0xF7 / 255.0, blue: 0xF7 / 255.0, alpha: 1)
    }
}