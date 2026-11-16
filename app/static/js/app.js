(function () {
    const $ = (s, r = document) => r.querySelector(s);
    const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

    /* ---------- Reveal on scroll, staggered per section ---------- */
    const reveals = $$(".reveal");
    if ("IntersectionObserver" in window) {
        const groups = new Map();
        reveals.forEach((el) => {
            const parent = el.closest("section") || document.body;
            const i = groups.get(parent) || 0;
            el.style.setProperty("--d", `${Math.min(i, 8) * 80}ms`);
            groups.set(parent, i + 1);
        });
        const io = new IntersectionObserver((entries) => {
            entries.forEach((e) => {
                if (e.isIntersecting) { e.target.classList.add("is-in"); io.unobserve(e.target); }
            });
        }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
        reveals.forEach((el) => io.observe(el));
    } else {
        reveals.forEach((el) => el.classList.add("is-in"));
    }

    /* ---------- Pipeline track fills as you scroll ---------- */
    const pipe = $("[data-pipeline]");
    if (pipe) {
        const steps = $$(".pipeline__step", pipe);
        const update = () => {
            const r = pipe.getBoundingClientRect();
            const vh = innerHeight;
            const prog = Math.min(1, Math.max(0, (vh * 0.8 - r.top) / (vh * 0.5)));
            pipe.style.setProperty("--progress", prog.toFixed(3));
            steps.forEach((s, i) => s.classList.toggle("is-lit", prog >= i / steps.length + 0.02));
        };
        addEventListener("scroll", update, { passive: true });
        addEventListener("resize", update);
        update();
    }

    /* ---------- Sample transcript / summary toggle ---------- */
    const sample = $("[data-sample]");
    if (sample) {
        const tabs = $$("[data-view]", sample);
        const toggle = $(".toggle", sample);
        const panels = Object.fromEntries($$("[data-panel]", sample).map((p) => [p.dataset.panel, p]));
        const stat = (k) => $(`[data-stat="${k}"]`);
        const words = (el) => el.textContent.trim().split(/\s+/).length;
        const total = words(panels.transcript);

        function animateNumber(el, to, fmt) {
            const from = parseFloat(el.dataset.v || 0);
            const start = performance.now();
            const dur = 700;
            el.dataset.v = to;
            (function step(now) {
                const k = Math.min(1, (now - start) / dur);
                const e = 1 - Math.pow(1 - k, 3);
                el.textContent = fmt(from + (to - from) * e);
                if (k < 1) requestAnimationFrame(step);
            })(start);
        }

        function show(view) {
            tabs.forEach((t) => {
                const on = t.dataset.view === view;
                t.setAttribute("aria-selected", on);
                t.tabIndex = on ? 0 : -1;
            });
            Object.entries(panels).forEach(([k, p]) => { p.hidden = k !== view; });
            toggle.dataset.active = view;
            const n = words(panels[view]);
            animateNumber(stat("words"), n, (v) => Math.round(v).toLocaleString());
            animateNumber(stat("time"), n / 230 * 60, (v) => v >= 60 ? `${(v / 60).toFixed(1)} min` : `${Math.round(v)} s`);
            animateNumber(stat("kept"), n / total * 100, (v) => `${Math.round(v)}%`);
        }

        tabs.forEach((t) => {
            t.addEventListener("click", () => show(t.dataset.view));
            t.addEventListener("keydown", (e) => {
                if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
                const next = tabs[(tabs.indexOf(t) + 1) % tabs.length];
                next.focus();
                show(next.dataset.view);
            });
        });
        show("transcript");
    }

    /* ---------- Upload: drag & drop + progress, then open the lecture page ---------- */
    const form = $("[data-upload]");
    if (form) {
        const drop = $("[data-drop]", form);
        const input = $("input[type=file]", drop);
        const text = $("[data-drop-text]", form);
        const progress = $("[data-progress]", form);
        const bar = $("[data-progress-bar]", form);
        const ptext = $("[data-progress-text]", form);
        const btn = $("[data-upload-btn]", form);
        const original = text.innerHTML;
        const btnLabel = btn.textContent;

        const fmtSize = (b) => b > 1e9 ? `${(b / 1e9).toFixed(2)} GB` : `${(b / 1e6).toFixed(1)} MB`;
        const sync = () => {
            const f = input.files[0];
            drop.classList.toggle("has-file", !!f);
            text.innerHTML = original;
            if (f) text.textContent = `${f.name} · ${fmtSize(f.size)}`;
        };
        input.addEventListener("change", sync);
        ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("is-over"); }));
        ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove("is-over")));
        drop.addEventListener("drop", (e) => {
            e.preventDefault();
            if (e.dataTransfer.files.length) { input.files = e.dataTransfer.files; sync(); }
        });

        const fail = (msg) => {
            ptext.textContent = msg;
            bar.style.width = "0";
            btn.disabled = false;
            btn.textContent = btnLabel;
        };

        form.addEventListener("submit", (e) => {
            if (!input.files.length) return; // let the browser show "required"
            e.preventDefault();
            const xhr = new XMLHttpRequest();
            xhr.open("POST", form.action);
            xhr.setRequestHeader("Accept", "application/json");
            progress.hidden = false;
            btn.disabled = true;
            btn.textContent = "Uploading…";
            xhr.upload.addEventListener("progress", (ev) => {
                if (!ev.lengthComputable) return;
                const pct = Math.round((ev.loaded / ev.total) * 100);
                bar.style.width = pct + "%";
                ptext.textContent = pct < 100 ? `Uploading… ${pct}%` : "Upload complete. Starting the pipeline…";
            });
            xhr.addEventListener("load", () => {
                if (/\/login(\?|$)/.test(xhr.responseURL)) { location.href = xhr.responseURL; return; }
                let data = null;
                try { data = JSON.parse(xhr.responseText); } catch (_) { /* not JSON */ }
                if (xhr.status < 400 && data && data.url) { location.href = data.url; return; }
                fail((data && data.error) || (xhr.status === 413 ? "That file is larger than 2 GB." : `Upload failed (${xhr.status}). Try again.`));
            });
            xhr.addEventListener("error", () => fail("Upload failed. Check that the server is running and try again."));
            xhr.send(new FormData(form));
        });
    }

    /* ---------- Live status: library rows ---------- */
    const FINAL = ["done", "failed"];

    $$("[data-poll]").forEach((row) => {
        const badge = $("[data-status]", row);
        const tick = async () => {
            try {
                const res = await fetch(row.dataset.poll, { headers: { Accept: "application/json" } });
                if (res.ok) {
                    const d = await res.json();
                    badge.className = `status status--${d.status}`;
                    badge.textContent = d.status_label;
                    if (FINAL.includes(d.status)) {
                        $(".lecture-row__preview", row).textContent = d.summary
                            ? d.summary.slice(0, 140) + (d.summary.length > 140 ? "…" : "")
                            : "Processing failed. Open for details.";
                        return;
                    }
                }
            } catch (_) { /* retry */ }
            setTimeout(tick, 3000);
        };
        setTimeout(tick, 1500);
    });

    /* ---------- Live status: lecture page while processing ---------- */
    const working = $("[data-working]");
    if (working) {
        const order = ["queued", "extracting", "transcribing", "summarizing", "done"];
        const label = $("[data-working-label]", working);
        const stages = $$("[data-stage]", working);
        const tick = async () => {
            try {
                const res = await fetch(working.dataset.working, { headers: { Accept: "application/json" } });
                if (res.ok) {
                    const d = await res.json();
                    if (FINAL.includes(d.status)) { location.reload(); return; }
                    const cur = order.indexOf(d.status);
                    stages.forEach((s) => {
                        const i = order.indexOf(s.dataset.stage);
                        s.classList.toggle("is-done", i < cur);
                        s.classList.toggle("is-active", i === cur);
                    });
                    label.textContent = `${d.status_label}…`;
                    const badge = $("[data-status-badge]");
                    if (badge) { badge.className = `status status--${d.status} status--lg`; badge.textContent = d.status_label; }
                }
            } catch (_) { /* retry */ }
            setTimeout(tick, 2500);
        };
        setTimeout(tick, 1500);
    }

    /* ---------- Copy buttons ---------- */
    $$("[data-copy]").forEach((btn) => {
        btn.addEventListener("click", async () => {
            const src = $(btn.dataset.copy);
            const label = btn.textContent;
            try {
                await navigator.clipboard.writeText(src.innerText.trim());
                btn.textContent = "Copied";
            } catch (_) {
                btn.textContent = "Press Ctrl+C";
                const range = document.createRange();
                range.selectNodeContents(src);
                getSelection().removeAllRanges();
                getSelection().addRange(range);
            }
            setTimeout(() => { btn.textContent = label; }, 1600);
        });
    });

    /* ---------- Confirm destructive forms ---------- */
    $$("form[data-confirm]").forEach((f) => {
        f.addEventListener("submit", (e) => { if (!confirm(f.dataset.confirm)) e.preventDefault(); });
    });
})();
