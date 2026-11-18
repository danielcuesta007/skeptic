// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "skeptic-handoff-dialog",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "skeptic-handoff-dialog",
            path: "Sources"
        ),
    ]
)