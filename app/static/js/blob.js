/* Liquid-metal blob: a ray-marched metaball with chrome reflections and
   a thin-film iridescent sheen. One WebGL context per [data-blob] element.
   Falls back to a CSS blob when WebGL is unavailable. */
(function () {
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

    const VERT = `
attribute vec2 p;
void main() { gl_Position = vec4(p, 0.0, 1.0); }`;

    const FRAG = `
precision highp float;
uniform vec2  uRes;
uniform float uTime;
uniform vec2  uMouse;
uniform float uSeed;

float smin(float a, float b, float k) {
    float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
    return mix(b, a, h) - k * h * (1.0 - h);
}

float map(vec3 p) {
    float t = uTime * 0.35 + uSeed;
    float d = length(p - vec3(sin(t) * 0.25, cos(t * 0.8) * 0.12, 0.0)) - 0.95;
    d = smin(d, length(p - vec3(0.55 + cos(t * 0.7) * 0.2, 0.42 + sin(t * 1.1) * 0.15, sin(t * 0.5) * 0.3)) - 0.58, 0.55);
    d = smin(d, length(p - vec3(-0.62 + sin(t * 0.9) * 0.2, 0.18 + cos(t * 0.6) * 0.15, cos(t * 0.6) * 0.3)) - 0.62, 0.55);
    d = smin(d, length(p - vec3(cos(t * 0.45) * 0.4, -0.55, sin(t * 0.8) * 0.2)) - 0.55, 0.6);
    d += 0.035 * sin(3.1 * p.x + t * 2.0) * sin(2.7 * p.y + t * 1.6) * sin(3.3 * p.z + t * 1.2);
    d += 0.008 * sin(7.3 * p.x - t * 1.4) * sin(6.1 * p.y + t * 1.1);
    return d;
}

vec3 calcNormal(vec3 p) {
    vec2 e = vec2(0.0015, 0.0);
    return normalize(vec3(
        map(p + e.xyy) - map(p - e.xyy),
        map(p + e.yxy) - map(p - e.yxy),
        map(p + e.yyx) - map(p - e.yyx)));
}

// A dark studio: warm amber softboxes overhead, a cold blue floor,
// bright white strips on the sides — what the chrome reflects.
vec3 env(vec3 r) {
    vec3 c = vec3(0.003, 0.003, 0.005);
    // overhead amber softbox (small, very bright)
    float top = smoothstep(0.6, 0.8, r.y);
    float boxes = smoothstep(0.16, 0.05, abs(r.x + 0.32)) + smoothstep(0.12, 0.04, abs(r.x - 0.38)) * 0.8;
    c += vec3(1.0, 0.58, 0.14) * top * boxes * 2.6;
    c += vec3(0.25, 0.14, 0.05) * top * 0.25;
    // thin warm strips that draw the gold arcs across the top
    c += vec3(1.0, 0.72, 0.30) * pow(max(0.0, 1.0 - abs(r.y - 0.36) * 9.0), 6.0) * smoothstep(-0.2, 0.6, r.x) * 2.0;
    c += vec3(1.0, 0.62, 0.20) * pow(max(0.0, 1.0 - abs(r.y - 0.05) * 12.0), 6.0) * smoothstep(0.1, -0.7, r.x) * 1.4;
    // cold blue floor panel
    c += vec3(0.10, 0.30, 1.0) * smoothstep(-0.5, -0.72, r.y) * (0.3 + smoothstep(0.15, 0.7, abs(r.x))) * 1.5;
    // crisp white side strips — the bright rims
    c += vec3(1.0) * smoothstep(0.86, 0.94, abs(r.x)) * smoothstep(-0.7, 0.2, r.y) * 2.2;
    // a faint magenta bounce from behind
    c += vec3(0.7, 0.2, 0.35) * smoothstep(0.5, 1.0, -r.z) * 0.2;
    return c;
}

mat2 rot(float a) { float s = sin(a), c = cos(a); return mat2(c, -s, s, c); }

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * uRes) / min(uRes.x, uRes.y * 1.25) * 1.25;
    vec3 ro = vec3(0.0, 0.18, 4.1);
    vec3 rd = normalize(vec3(uv, -1.55));

    float t = 0.0, d = 0.0, minD = 1e5;
    bool hit = false;
    for (int i = 0; i < 90; i++) {
        vec3 p = ro + rd * t;
        d = map(p);
        minD = min(minD, d);
        if (d < 0.001) { hit = true; break; }
        t += d * 0.9;
        if (t > 8.0) break;
    }

    // soft, anti-aliased silhouette: near-misses become a thin bright rim
    if (!hit) {
        float a = 1.0 - smoothstep(0.0, 0.012, minD);
        gl_FragColor = vec4(vec3(0.85, 0.82, 0.78) * a, a);
        return;
    }

    vec3 p = ro + rd * t;
    vec3 n = calcNormal(p);
    vec3 r = reflect(rd, n);
    r.xz *= rot(uMouse.x * 0.6 + sin(uTime * 0.1) * 0.25);
    r.yz *= rot(uMouse.y * 0.3);

    float fres = pow(1.0 - max(dot(-rd, n), 0.0), 3.0);
    vec3 col = env(r) * (0.45 + 0.7 * fres);

    // thin-film iridescence, strongest at grazing angles
    vec3 film = 0.5 + 0.5 * cos(6.2831 * (fres * 1.4 + n.y * 0.25 + vec3(0.0, 0.33, 0.67) + uTime * 0.03));
    col = mix(col, col * film * 1.8, 0.2 + 0.25 * fres);

    // bright rim like polished metal catching a backlight
    col += vec3(1.0, 0.97, 0.92) * pow(fres, 2.2) * 0.9;

    col *= 1.15;
    col = col / (1.0 + col);           // tone map
    col = pow(col, vec3(1.0 / 2.2));   // gamma

    gl_FragColor = vec4(col, 1.0);
}`;

    function compile(gl, type, src) {
        const s = gl.createShader(type);
        gl.shaderSource(s, src);
        gl.compileShader(s);
        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
            console.warn(gl.getShaderInfoLog(s));
            return null;
        }
        return s;
    }

    const mouse = { x: 0, y: 0, tx: 0, ty: 0 };
    addEventListener("pointermove", (e) => {
        mouse.tx = (e.clientX / innerWidth - 0.5) * 2;
        mouse.ty = (e.clientY / innerHeight - 0.5) * 2;
    }, { passive: true });

    const blobs = [];

    function setup(el) {
        const canvas = el.querySelector("canvas");
        const gl = canvas && canvas.getContext("webgl", { premultipliedAlpha: false, alpha: true, antialias: true });
        if (!gl) { el.classList.add("is-fallback"); return; }

        const vs = compile(gl, gl.VERTEX_SHADER, VERT);
        const fs = compile(gl, gl.FRAGMENT_SHADER, FRAG);
        if (!vs || !fs) { el.classList.add("is-fallback"); return; }

        const prog = gl.createProgram();
        gl.attachShader(prog, vs);
        gl.attachShader(prog, fs);
        gl.linkProgram(prog);
        if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) { el.classList.add("is-fallback"); return; }
        gl.useProgram(prog);

        const buf = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, buf);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
        const loc = gl.getAttribLocation(prog, "p");
        gl.enableVertexAttribArray(loc);
        gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);

        const u = {
            res: gl.getUniformLocation(prog, "uRes"),
            time: gl.getUniformLocation(prog, "uTime"),
            mouse: gl.getUniformLocation(prog, "uMouse"),
            seed: gl.getUniformLocation(prog, "uSeed"),
        };
        gl.uniform1f(u.seed, parseFloat(el.dataset.blobSeed || "0"));

        const blob = { el, canvas, gl, u, visible: true };

        function resize() {
            const rect = canvas.getBoundingClientRect();
            // cap the pixel budget: a ray-marcher per pixel is expensive on big screens
            const budget = 1.1e6;
            const dpr = Math.min(window.devicePixelRatio || 1, 1.5, Math.sqrt(budget / Math.max(1, rect.width * rect.height)));
            canvas.width = Math.max(1, Math.round(rect.width * dpr));
            canvas.height = Math.max(1, Math.round(rect.height * dpr));
            gl.viewport(0, 0, canvas.width, canvas.height);
            gl.uniform2f(u.res, canvas.width, canvas.height);
            if (reduced) render(blob, 4000);
        }
        resize();
        new ResizeObserver(resize).observe(canvas);
        new IntersectionObserver(([e]) => { blob.visible = e.isIntersecting; }, { rootMargin: "100px" }).observe(el);
        blobs.push(blob);
        render(blob, reduced ? 4000 : 0);
    }

    function render(b, t) {
        const { gl, u } = b;
        gl.uniform1f(u.time, t / 1000);
        gl.uniform2f(u.mouse, mouse.x, mouse.y);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
    }

    function loop(t) {
        mouse.x += (mouse.tx - mouse.x) * 0.04;
        mouse.y += (mouse.ty - mouse.y) * 0.04;
        for (const b of blobs) if (b.visible) render(b, t);
        requestAnimationFrame(loop);
    }

    document.querySelectorAll("[data-blob]").forEach(setup);
    if (!reduced && blobs.length) requestAnimationFrame(loop);
})();
