import SwiftUI

/// Same hood geometry as Vitals `SkepticMark` (brand guide v1).
enum HoodMark {
    static func hood(_ s: CGFloat) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: s * 0.50, y: s * 0.08))
        p.addCurve(
            to: CGPoint(x: s * 0.20, y: s * 0.68),
            control1: CGPoint(x: s * 0.23, y: s * 0.23),
            control2: CGPoint(x: s * 0.15, y: s * 0.43)
        )
        p.addLine(to: CGPoint(x: s * 0.08, y: s * 0.92))
        p.addQuadCurve(to: CGPoint(x: s * 0.92, y: s * 0.92), control: CGPoint(x: s * 0.50, y: s * 0.80))
        p.addLine(to: CGPoint(x: s * 0.80, y: s * 0.68))
        p.addCurve(
            to: CGPoint(x: s * 0.50, y: s * 0.08),
            control1: CGPoint(x: s * 0.85, y: s * 0.43),
            control2: CGPoint(x: s * 0.77, y: s * 0.23)
        )
        p.closeSubpath()
        p.move(to: CGPoint(x: s * 0.50, y: s * 0.32))
        p.addCurve(
            to: CGPoint(x: s * 0.34, y: s * 0.61),
            control1: CGPoint(x: s * 0.35, y: s * 0.41),
            control2: CGPoint(x: s * 0.31, y: s * 0.49)
        )
        p.addQuadCurve(to: CGPoint(x: s * 0.50, y: s * 0.75), control: CGPoint(x: s * 0.38, y: s * 0.70))
        p.addQuadCurve(to: CGPoint(x: s * 0.66, y: s * 0.61), control: CGPoint(x: s * 0.62, y: s * 0.70))
        p.addCurve(
            to: CGPoint(x: s * 0.50, y: s * 0.32),
            control1: CGPoint(x: s * 0.69, y: s * 0.49),
            control2: CGPoint(x: s * 0.65, y: s * 0.41)
        )
        p.closeSubpath()
        return p
    }
}

struct HoodHalftoneView: View {
    var size: CGFloat = 52
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: size * 0.22, style: .continuous)
                .fill(SkepticBrand.ink)
            Canvas { ctx, canvasSize in
                let s = min(canvasSize.width, canvasSize.height) * 0.78
                ctx.translateBy(x: (canvasSize.width - s) / 2, y: (canvasSize.height - s) / 2)
                ctx.clip(to: HoodMark.hood(s), style: FillStyle(eoFill: true))
                let step = max(2.0, s * 0.08)
                var y: CGFloat = 0
                var row = 0
                while y < s {
                    var x: CGFloat = row % 2 == 0 ? 0 : step / 2
                    while x < s {
                        let r = step * 0.40 * (0.55 + 0.45 * (1 - y / s))
                        ctx.fill(
                            Path(ellipseIn: CGRect(x: x - r, y: y - r, width: r * 2, height: r * 2)),
                            with: .color(.white)
                        )
                        x += step
                    }
                    y += step * 0.87
                    row += 1
                }
            }
            .frame(width: size, height: size)
        }
        .frame(width: size, height: size)
    }
}