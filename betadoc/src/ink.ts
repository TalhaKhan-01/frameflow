// Night-edition background: domain-warped fbm "ink in water" with a cursor ripple. Raw WebGL, no library.
// setChaos(0..1) is driven by scroll (Problem section = chaos). Reduced motion: one still frame.
const VERT = `#version 300 es
in vec2 p; void main(){ gl_Position = vec4(p, 0., 1.); }`;
const FRAG = `#version 300 es
precision highp float;
uniform vec2 uRes; uniform float uTime; uniform vec2 uMouse; uniform float uChaos;
out vec4 o;
float h(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float n(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.-2.*f);
  return mix(mix(h(i), h(i+vec2(1,0)), f.x), mix(h(i+vec2(0,1)), h(i+vec2(1,1)), f.x), f.y); }
float fbm(vec2 p){ float v = 0., a = .5; for (int i = 0; i < 5; i++){ v += a*n(p); p = p*2.03 + 17.; a *= .5; } return v; }
void main(){
  vec2 uv = gl_FragCoord.xy / uRes; vec2 p = (gl_FragCoord.xy - .5*uRes) / uRes.y;
  float t = uTime * (.035 + .08*uChaos);
  vec2 m = (uMouse - .5*uRes) / uRes.y; float d = length(p - m);
  p += .06 * exp(-d*5.) * vec2(sin(d*24. - uTime*2.), cos(d*24. - uTime*2.));
  vec2 q = vec2(fbm(p*1.6 + t), fbm(p*1.6 - t + 4.));
  vec2 r = vec2(fbm(p*1.8 + q*(1.5 + 2.5*uChaos) + vec2(1.7, 9.2) + t), fbm(p*1.8 + q*1.8 + vec2(8.3, 2.8)));
  float f = fbm(p*2. + r*1.6);
  vec3 night = vec3(.075, .078, .125), ink = vec3(.16, .15, .27), red = vec3(.78, .25, .2), lamp = vec3(.93, .74, .42);
  vec3 c = mix(night, ink, smoothstep(.25, .85, f));
  c = mix(c, red, smoothstep(.62, .95, f*r.x) * (.18 + .3*uChaos));
  c += lamp * pow(smoothstep(.55, 1., q.y*f), 3.) * .22;
  float g = h(gl_FragCoord.xy + floor(uTime*12.)) - .5; c += g * .035;
  c *= 1. - .55*pow(length(uv - .5)*1.25, 2.2);
  o = vec4(c, 1.);
}`;

export function ink(canvas: HTMLCanvasElement, still: boolean) {
  const gl = canvas.getContext("webgl2", { antialias: false, powerPreference: "low-power" });
  if (!gl) { canvas.classList.add("fallback"); return { setChaos: (_: number) => {} }; }
  const sh = (type: number, src: string) => { const s = gl.createShader(type)!; gl.shaderSource(s, src); gl.compileShader(s); return s; };
  const prog = gl.createProgram()!;
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, VERT)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FRAG)); gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) { canvas.classList.add("fallback"); return { setChaos: (_: number) => {} }; }
  gl.useProgram(prog);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, "p"); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const u = (k: string) => gl.getUniformLocation(prog, k);
  const uRes = u("uRes"), uTime = u("uTime"), uMouse = u("uMouse"), uChaos = u("uChaos");
  const scale = Math.min(devicePixelRatio, 1.5) * 0.6;   // the field is soft: render at reduced resolution
  let chaos = 0, target = 0, mx = innerWidth * 0.7, my = innerHeight * 0.4, sx = mx, sy = my, visible = true;
  const size = () => { canvas.width = Math.round(innerWidth * scale); canvas.height = Math.round(innerHeight * scale); gl.viewport(0, 0, canvas.width, canvas.height); };
  size(); addEventListener("resize", size);
  addEventListener("pointermove", (e) => { mx = e.clientX; my = innerHeight - e.clientY; }, { passive: true });
  document.addEventListener("visibilitychange", () => { visible = !document.hidden; if (visible && !still) requestAnimationFrame(frame); });
  const t0 = performance.now();
  function draw(t: number) {
    sx += (mx - sx) * 0.06; sy += (my - sy) * 0.06; chaos += (target - chaos) * 0.04;
    gl!.uniform2f(uRes, canvas.width, canvas.height); gl!.uniform1f(uTime, t);
    gl!.uniform2f(uMouse, sx * scale, sy * scale); gl!.uniform1f(uChaos, chaos);
    gl!.drawArrays(gl!.TRIANGLES, 0, 3);
  }
  function frame(now: number) { if (!visible) return; draw((now - t0) / 1000); requestAnimationFrame(frame); }
  if (still) draw(12); else requestAnimationFrame(frame);
  return { setChaos: (v: number) => { target = v; if (still) { chaos = v; draw(12); } } };
}
