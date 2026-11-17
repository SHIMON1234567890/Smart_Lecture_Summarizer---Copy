/* Twinkling starfield for every <canvas data-stars="N"> */
(function () {
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const fields = [];

    function setup(canvas) {
        const count = parseInt(canvas.dataset.stars, 10) || 80;
        const ctx = canvas.getContext("2d");
        let stars = [];
        let w = 0, h = 0, dpr = 1;

        function resize() {
            dpr = Math.min(window.devicePixelRatio || 1, 2);
            const rect = canvas.getBoundingClientRect();
            w = rect.width; h = rect.height;
            canvas.width = Math.round(w * dpr);
            canvas.height = Math.round(h * dpr);
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            // density scales with area so phones aren't overcrowded
            const n = Math.round(count * Math.min(1, (w * h) / (1440 * 900)) + count * 0.25);
            stars = Array.from({ length: n }, () => ({
                x: Math.random() * w,
                y: Math.random() * h,
                r: Math.random() < 0.08 ? 1.4 + Math.random() * 0.8 : 0.4 + Math.random() * 0.8,
                a: 0.25 + Math.random() * 0.7,
                s: 0.4 + Math.random() * 1.6,
                p: Math.random() * Math.PI * 2,
                vy: 0.02 + Math.random() * 0.05,
            }));
        }

        function draw(t) {
            ctx.clearRect(0, 0, w, h);
            for (const s of stars) {
                const tw = reduced ? 1 : 0.55 + 0.45 * Math.sin(t * 0.001 * s.s + s.p);
                if (!reduced) {
                    s.y -= s.vy;
                    if (s.y < -2) { s.y = h + 2; s.x = Math.random() * w; }
                }
                ctx.globalAlpha = s.a * tw;
                ctx.fillStyle = "#fff";
                ctx.beginPath();
                ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
                ctx.fill();
            }
            ctx.globalAlpha = 1;
        }

        resize();
        const field = { canvas, draw, resize, visible: true };
        fields.push(field);
        new ResizeObserver(resize).observe(canvas);
        new IntersectionObserver(([e]) => { field.visible = e.isIntersecting; }).observe(canvas);
        draw(0);
    }

    function loop(t) {
        for (const f of fields) if (f.visible) f.draw(t);
        requestAnimationFrame(loop);
    }

    document.querySelectorAll("canvas[data-stars]").forEach(setup);
    if (!reduced && fields.length) requestAnimationFrame(loop);
})();
