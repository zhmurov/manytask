/* No dependencies or network requests. All decoration is disposable. */
function winterIsUrgent(deadline, now) {
    const remaining = Number(deadline) * 1000 - now;
    return remaining > 0 && remaining < 86400000;
}

function winterSnowEdge(width, radius, depths, x) {
    radius = Math.min(radius, width / 2);
    const corner = Math.max(0, radius - Math.min(x, width - x));
    const base = radius - Math.sqrt(Math.max(0, radius * radius - corner * corner));
    const position = Math.max(0, Math.min(1, x / width)) * (depths.length - 1);
    const index = Math.floor(position);
    const blend = (1 - Math.cos((position - index) * Math.PI)) / 2;
    const depth = depths[index] * (1 - blend) + depths[Math.min(index + 1, depths.length - 1)] * blend;
    const taper = Math.min(1, x / Math.max(radius, 1), (width - x) / Math.max(radius, 1));
    return {base, top: base - depth * taper, depth: depth * taper};
}

function winterSnowContour(width, radius, depths) {
    const upper = [];
    const lower = [];
    const steps = Math.ceil(width / 3);
    for (let index = 0; index <= steps; index++) {
        const x = width * index / steps;
        const edge = winterSnowEdge(width, radius, depths, x);
        // The 14px drawing margin sits above the actual rounded border.
        upper.push(`${x.toFixed(2)}px ${(14 + edge.top).toFixed(2)}px`);
        lower.unshift(`${x.toFixed(2)}px ${(14 + edge.base + Math.min(.8, edge.depth)).toFixed(2)}px`);
    }
    return `polygon(${upper.concat(lower).join(',')})`;
}

function winterDepositSnow(depths, fraction, amount) {
    const center = Math.max(0, Math.min(1, fraction)) * (depths.length - 1);
    return depths.map((depth, index) => Math.min(9, depth + amount * Math.exp(-((index - center) ** 2) / 1.4)));
}

function winterSnowState(snow, ice, urgent, seconds, deposit = 0) {
    const melted = urgent ? Math.min(snow + deposit, seconds * .6) : 0;
    return {
        snow: Math.max(0, Math.min(9, snow + deposit - melted)),
        ice: urgent ? Math.min(17, ice + melted * 1.8) : Math.max(0, ice - seconds),
    };
}

(() => {
    'use strict';
    const world = document.getElementById('new-year-world');
    const toggles = Array.from(document.querySelectorAll('[data-new-year-toggle]'));
    if (!world || !toggles.length) return;

    const root = document.documentElement;
    const canvas = world.querySelector('canvas');
    const footer = world.querySelector('.winter-footer');
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const storageKey = 'manytask-new-year';
    const records = new Map();
    let enabled = true;
    let frame = null;
    let lastFrame = 0;
    let lastSurvey = 0;
    let dirty = true;
    let visibleSurfaces = [];
    let flakes = [];
    let ground = 24;
    let context;
    let width = 0;
    let height = 0;

    try { enabled = localStorage.getItem(storageKey) !== 'off'; } catch { /* Storage is optional. */ }

    function paintCap(record) {
        record.cap.style.setProperty('--snow-depth', `${record.snow}px`);
        record.cap.style.setProperty('--ice-depth', `${record.ice}px`);
        record.drift.style.clipPath = winterSnowContour(record.width, record.radius, record.depths);
        record.element.classList.toggle('winter-melting', record.urgent);
    }

    function survey() {
        const now = Date.now();
        const elements = document.querySelectorAll('.mt-task-card, .task-deadline');
        const current = new Set(elements);
        for (const [element, record] of records) {
            if (!current.has(element)) {
                record.cap.remove();
                element.classList.remove('winter-surface', 'winter-melting');
                records.delete(element);
            }
        }
        visibleSurfaces = [];
        elements.forEach(element => {
            let record = records.get(element);
            if (!record) {
                const cap = document.createElement('span');
                cap.className = 'winter-snowcap';
                cap.setAttribute('aria-hidden', 'true');
                const drift = document.createElement('span');
                drift.className = 'winter-drift';
                cap.append(drift);
                element.append(cap);
                element.classList.add('winter-surface');
                const snow = motion.matches ? 7 : 3;
                const seed = Math.random() * Math.PI * 2;
                const depths = Array.from({length: 17}, (_, index) => snow * (.8 + .2 * Math.sin(index * 1.7 + seed)));
                record = {element, cap, drift, depths, snow, ice: 0};
                records.set(element, record);
            }
            // Graphs expose all breakpoints, so urgency also updates while the page stays open.
            let deadline = element.dataset.winterDeadline;
            const graph = element.querySelector('.deadline-graph-canvas');
            if (graph) {
                try {
                    deadline = JSON.parse(graph.dataset.points).map(point => point.ts)
                        .find(time => time * 1000 > now);
                } catch { /* A malformed graph should not interrupt the rest of the page. */ }
            }
            record.urgent = winterIsUrgent(deadline, now);
            if (motion.matches) record.ice = record.urgent ? 12 : 0;
            record.rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            record.width = element.offsetWidth || record.rect.width || 180;
            record.radius = Math.min(24, parseFloat(style.borderTopLeftRadius) || 12);
            const border = parseFloat(style.borderTopWidth) || 0;
            record.cap.style.top = `${-14 - border}px`;
            record.cap.style.left = `${-border}px`;
            record.cap.style.width = `${record.width}px`;
            record.cap.style.setProperty('--snow-rim', `${record.radius + 3}px`);
            paintCap(record);
            if (record.rect.width > 0 && record.rect.height > 0 && record.rect.bottom > 0 && record.rect.top < height) {
                visibleSurfaces.push(record);
            }
        });
        footer.style.setProperty('--winter-ground', `${ground}px`);
        dirty = false;
    }

    function newFlake(scatter = false) {
        return {
            x: Math.random() * width,
            y: scatter ? Math.random() * height : -10,
            radius: .9 + Math.random() * 2.3,
            speed: 24 + Math.random() * 35,
            drift: Math.random() * Math.PI * 2,
        };
    }

    function resize() {
        width = document.documentElement.clientWidth;
        height = window.innerHeight;
        const ratio = Math.min(window.devicePixelRatio || 1, 2);
        canvas.width = Math.round(width * ratio);
        canvas.height = Math.round(height * ratio);
        context?.setTransform(ratio, 0, 0, ratio, 0, 0);
        const ballRadius = width <= 700 ? 22.5 : 30 * 200 / 220;
        footer.style.setProperty('--winter-roll-turns', `${(width + 240) / (2 * Math.PI * ballRadius)}turn`);
        flakes = Array.from({length: width < 600 ? 35 : 75}, () => newFlake(true));
        dirty = true;
    }

    function animate(time) {
        frame = null;
        if (!enabled || motion.matches || document.hidden || !context) return;
        const seconds = lastFrame ? Math.min((time - lastFrame) / 1000, .05) : 0;
        lastFrame = time;
        // Cache geometry between surveys; no layout reads inside the particle loop.
        if (dirty || time - lastSurvey > 250) {
            survey();
            lastSurvey = time;
        }
        context.clearRect(0, 0, width, height);
        context.fillStyle = root.getAttribute('data-bs-theme') === 'dark' ? '#e5f5ff' : '#91b9cd';
        for (let index = 0; index < flakes.length; index++) {
            const flake = flakes[index];
            flake.y += flake.speed * seconds;
            flake.x += Math.sin(time / 1800 + flake.drift) * 13 * seconds;
            flake.x = (flake.x + width) % width;
            // Foreground flakes pass every plank and only recycle below the viewport.
            if (flake.y > height + flake.radius) {
                flakes[index] = newFlake();
                continue;
            }
            context.globalAlpha = .35 + flake.radius / 6;
            context.beginPath();
            context.arc(flake.x, flake.y, flake.radius, 0, Math.PI * 2);
            context.fill();
        }
        // Accumulation is a separate, time-driven effect; no particles are consumed.
        ground = Math.min(48, ground + seconds * .12);
        for (const record of visibleSurfaces) {
            record.depths = winterDepositSnow(record.depths, Math.random(), seconds * .9);
            record.snow = Math.max(...record.depths);
        }
        for (const record of records.values()) {
            if (!record.urgent && !record.ice) continue;
            const average = record.depths.reduce((sum, depth) => sum + depth, 0) / record.depths.length;
            const state = winterSnowState(average, record.ice, record.urgent, seconds);
            if (record.urgent) record.depths = record.depths.map(depth => Math.max(0, depth - seconds * .6));
            record.snow = Math.max(...record.depths);
            record.ice = state.ice;
            // The next geometry survey paints this slow melt, at most four times a second.
        }
        frame = requestAnimationFrame(animate);
    }

    function stop() {
        if (frame !== null) cancelAnimationFrame(frame);
        frame = null;
        lastFrame = 0;
        context?.clearRect(0, 0, width, height);
    }

    function resume() {
        stop();
        root.classList.toggle('winter-paused', document.hidden);
        if (!enabled) return;
        survey();
        if (!motion.matches && !document.hidden && context) frame = requestAnimationFrame(animate);
    }

    const observer = new MutationObserver(() => { dirty = true; });
    const sizeObserver = new ResizeObserver(() => { dirty = true; });
    function apply() {
        stop();
        root.setAttribute('data-new-year', enabled ? 'on' : 'off');
        world.hidden = !enabled;
        toggles.forEach(toggle => {
            toggle.setAttribute('aria-pressed', String(enabled));
            toggle.querySelector('[data-new-year-status]').textContent = enabled ? 'On' : 'Off';
        });
        observer.disconnect();
        sizeObserver.disconnect();
        if (enabled) {
            try { context = canvas.getContext('2d'); } catch { /* Static scene remains available. */ }
            resize();
            const groups = document.getElementById('task-groups');
            if (groups) observer.observe(groups, {childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'hidden']});
            sizeObserver.observe(document.body);
            resume();
        } else {
            for (const record of records.values()) {
                record.cap.remove();
                record.element.classList.remove('winter-surface', 'winter-melting');
            }
            records.clear();
            visibleSurfaces = [];
            flakes = [];
            ground = 24;
            footer.style.removeProperty('--winter-ground');
        }
    }

    toggles.forEach(toggle => toggle.addEventListener('click', () => {
        enabled = !enabled;
        try { localStorage.setItem(storageKey, enabled ? 'on' : 'off'); } catch { /* Keep the in-page choice. */ }
        apply();
    }));
    window.addEventListener('storage', event => {
        if (event.key === storageKey || event.key === null) {
            enabled = event.newValue !== 'off';
            apply();
        }
    });
    window.addEventListener('resize', () => { if (enabled) { resize(); resume(); } });
    window.addEventListener('scroll', () => { dirty = true; }, {passive: true});
    document.addEventListener('visibilitychange', resume);
    motion.addEventListener('change', resume);
    apply();
})();
