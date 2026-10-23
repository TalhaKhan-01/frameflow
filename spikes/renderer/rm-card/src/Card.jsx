import { AbsoluteFill, interpolate, Easing, useCurrentFrame } from "remotion";

const fade = (f, start, dur, from = 30) => ({
  opacity: interpolate(f, [start, start + dur], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
  transform: `translateY(${interpolate(f, [start, start + dur], [from, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) })}px)`,
});

export const Card = () => {
  const f = useCurrentFrame();
  const bar = interpolate(f, [39, 63], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.quad) });
  return (
    <AbsoluteFill style={{ background: "#0b0d12", color: "#f2f3f5", fontFamily: "ui-sans-serif, system-ui, sans-serif",
      justifyContent: "center", padding: "0 96px" }}>
      <div style={{ fontSize: 40, fontWeight: 700, letterSpacing: "0.18em", color: "#7dd3c0", ...fade(f, 6, 15) }}>INDIA vs DUBAI</div>
      <div style={{ fontSize: 128, lineHeight: 1.02, fontWeight: 800, letterSpacing: "-0.03em", ...fade(f, 14, 21, 80) }}>Same iPhone,</div>
      <div style={{ fontSize: 128, lineHeight: 1.02, fontWeight: 800, letterSpacing: "-0.03em", ...fade(f, 23, 21, 80) }}>₹20,000 more.</div>
      <div style={{ width: 520, height: 18, marginTop: 48, background: "#f6c177", transformOrigin: "left center", transform: `scaleX(${bar})` }} />
      <div style={{ marginTop: 40, fontSize: 44, color: "#a9afbd", opacity: interpolate(f, [57, 75], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
        Here's where the money goes.
      </div>
    </AbsoluteFill>
  );
};
