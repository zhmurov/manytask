const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const {test} = require('node:test');
const vm = require('node:vm');

const source = readFileSync(path.join(__dirname, '../../manytask/static/js/winter-mascot.js'), 'utf8');
const phases = ['leaving', 'fetching', 'returning', 'firing', 'returning-to-ball', 'rolling'];

function queue(options) {
    const context = vm.createContext({});
    vm.runInContext(source, context);
    return context.createWinterCelebrationQueue(options);
}

test('fetches and fires fireworks, then returns to the ball before another queued celebration', () => {
    const state = queue();
    state.enqueue(['one']);
    state.step(0);
    assert.equal(state.phase, 'leaving');
    state.step(100);
    state.step(100);
    assert.equal(state.phase, 'returning');
    state.enqueue(['two', 'three']);
    for (const phase of ['firing', 'returning-to-ball', 'rolling']) {
        state.step(100);
        assert.equal(state.phase, phase);
        assert.equal(state.pending, 2);
    }
    assert.equal(state.completed, 1);
    state.step(.2);
    assert.equal(state.phase, 'rolling');
    state.step(.3);
    assert.equal(state.phase, 'leaving');
    assert.equal(state.pending, 1);
    for (const phase of phases.slice(1)) { state.step(100); assert.equal(state.phase, phase); }
    state.step(1);
    assert.equal(state.phase, 'leaving');
    assert.equal(state.pending, 0);
    for (const phase of phases.slice(1)) { state.step(100); assert.equal(state.phase, phase); }
    assert.equal(state.completed, 3);
    state.step(100);
    assert.equal(state.phase, 'rolling');
});

test('waits for valid layout and clears an active and pending sequence on reset', () => {
    let laidOut = false;
    const state = queue({canStart: () => laidOut});
    state.enqueue(['two', 'three']);
    state.step(100);
    assert.equal(state.phase, 'rolling');
    assert.equal(state.pending, 2);
    laidOut = true;
    state.step(0);
    assert.equal(state.phase, 'leaving');
    state.reset();
    state.step(100);
    assert.equal(state.phase, 'rolling');
    assert.equal(state.pending, 0);
});

function scene(reduced = false, options = {}) {
    let pathWrites = 0;
    let geometryReads = 0;
    let lookups = 0;
    let paints = 0;
    let circles = 0;
    let dots = [];
    let maxBlur = 0;
    let clears = 0;
    function element() {
        const classes = new Set();
        return {
            style: {}, dataset: {}, attributes: {},
            setAttribute(name, value) { pathWrites++; this.attributes[name] = value; },
            classList: {add: name => classes.add(name), contains: name => classes.has(name),
                toggle(name, force) { if (force) classes.add(name); else classes.delete(name); }},
        };
    }
    const track = element();
    const roller = {...element(), getBoundingClientRect: () => ({...{left: 200, right: 400, width: 200}, ...options.roller})};
    const traveler = element();
    const facing = element();
    const pack = {...element(), getBoundingClientRect: () => { geometryReads++; return {...{left: 350, top: 720, width: 35}, ...options.pack}; }};
    const footer = {...element(), getBoundingClientRect: () => ({...{top: 1600, bottom: 1800}, ...options.footer})};
    let strokes = 0;
    let points = [];
    const canvas = {...element(), getContext: () => ({set shadowBlur(value) { maxBlur = Math.max(maxBlur, value); }, clearRect() { clears++; points = []; paints = circles = 0; dots = []; }, setTransform() {}, beginPath() {},
        moveTo() {}, lineTo(x, y) { points.push({x, y}); }, arc(x, y, radius) { circles++; if (radius < 2) dots.push({x, y}); }, fill() { paints++; }, stroke() { strokes++; paints++; }})};
    const upper = element();
    const backLeg = element();
    const frontLeg = element();
    const elements = {'.winter-mascot-upper': upper, '.winter-leg-back': backLeg, '.winter-leg-front': frontLeg, '.winter-roller-track': track, '.winter-roller': roller, '.winter-mascot-traveler': traveler,
        '.winter-mascot-facing': facing, '.winter-firework-pack': pack, '.winter-footer': footer, '.winter-fireworks': canvas};
    const world = {...element(), querySelector: selector => elements[selector]};
    const document = Object.assign(new EventTarget(), {hidden: false, documentElement: {clientWidth: 1000}, querySelectorAll: () => { lookups++; return options.cards || []; }});
    const window = Object.assign(new EventTarget(), {innerHeight: 800});
    const motion = Object.assign(new EventTarget(), {matches: reduced});
    const frames = new Map();
    let id = 0;
    const context = vm.createContext({document, window, requestAnimationFrame(callback) { frames.set(++id, callback); return id; },
        cancelAnimationFrame: frame => frames.delete(frame)});
    vm.runInContext(source, context);
    const mascot = context.initWinterMascot(world, motion);
    mascot.setEnabled(true);
    function changed(tasks = ['one']) { document.dispatchEvent(new CustomEvent('manytask:scores-changed', {detail: {tasks}})); }
    function advance(time) {
        if (!frames.size) return;
        const [key, callback] = frames.entries().next().value;
        frames.delete(key);
        callback(time);
    }
    return {document, window, motion, frames, track, traveler, facing, world, mascot, changed, advance, upper, backLeg, frontLeg, clears: () => clears, blur: () => maxBlur, paints: () => paints, circles: () => circles, dots: () => dots, reads: () => geometryReads, lookups: () => lookups, writes: () => pathWrites, strokes: () => strokes, points: () => points};
}

test('keeps the ball paused through fireworks and the walk back, then resumes rolling between queued tasks', () => {
    const page = scene();
    page.changed();
    page.advance(1000);
    assert.equal(page.world.dataset.winterCelebration, 'leaving');
    assert.equal(page.clears(), 0);
    assert.equal(page.track.classList.contains('winter-celebrating'), true);
    let queued = false;
    let returns = 0;
    let previous;
    for (let time = 1050; time <= 65000; time += 50) {
        page.advance(time);
        const phase = page.world.dataset.winterCelebration;
        if (phase === 'firing' && !queued) { page.changed(['two', 'three']); queued = true; }
        if (phase === 'rolling' && previous === 'returning-to-ball') {
            returns++;
            assert.equal(page.traveler.style.transform, '');
            assert.equal(page.track.classList.contains('winter-celebrating'), false);
        } else if (phase !== 'rolling') assert.equal(page.track.classList.contains('winter-celebrating'), true);
        previous = phase;
    }
    assert.equal(returns, 3);
    assert.ok(page.strokes() > 0);
    assert.equal(page.frames.size, 0);
});

test('pauses in a hidden tab and resumes from the same point', () => {
    const page = scene();
    page.changed();
    page.advance(1000);
    page.advance(1050);
    const position = page.traveler.style.transform;
    page.document.hidden = true;
    page.document.dispatchEvent(new Event('visibilitychange'));
    assert.equal(page.frames.size, 0);
    page.document.hidden = false;
    page.document.dispatchEvent(new Event('visibilitychange'));
    page.advance(100000);
    assert.equal(page.traveler.style.transform, position);
    page.advance(100050);
    assert.notEqual(page.traveler.style.transform, position);
});

test('disabling New Year mode or requesting reduced motion cancels celebrations and clears queued tasks', () => {
    for (const action of ['disable', 'reduce']) {
        const page = scene();
        page.changed(['one', 'two']);
        page.advance(1000);
        if (action === 'disable') page.mascot.setEnabled(false);
        else { page.motion.matches = true; page.motion.dispatchEvent(new Event('change')); }
        assert.equal(page.world.dataset.winterCelebration, 'rolling');
        assert.equal(page.track.classList.contains('winter-celebrating'), false);
        assert.equal(page.frames.size, 0);
        page.changed();
        assert.equal(page.frames.size, 0);
        page.motion.matches = false;
        page.mascot.setEnabled(true);
        assert.equal(page.frames.size, 0);
    }
    const reduced = scene(true);
    reduced.changed();
    assert.equal(reduced.frames.size, 0);
});


test('keeps task names and repeated updates in FIFO order until each return to the ball', () => {
    const started = [];
    const state = queue({onStart: name => { started.push(name); return {}; }});
    state.enqueue(['first', 'second', 'first']);
    for (const name of ['first', 'second', 'first']) {
        state.step(1);
        assert.equal(state.activeTask, name);
        for (const phase of phases.slice(1)) state.step(100);
        assert.equal(state.phase, 'rolling');
        assert.equal(state.activeTask, null);
    }
    assert.deepEqual(started, ['first', 'second', 'first']);
});

test('uses the closest edge, continues outward when already offscreen, and preserves the edge on resize', () => {
    const context = vm.createContext({});
    vm.runInContext(source, context);
    for (const [left, expected] of [[100, -1], [750, 1], [-600, -1], [1500, 1]]) {
        const route = context.winterMascotRoute({left, width: 200}, 1000);
        assert.equal(route.edge, expected);
        assert.ok(route.exit * expected >= 0);
        const exitCenter = left + 80 * route.scale + route.exit * route.scale;
        assert.ok(expected < 0 ? exitCenter <= -120 : exitCenter >= 1120);
    }
    assert.equal(context.winterMascotRoute({left: 100, width: 200}, 1000, 1).edge, 1);
});

test('aims at the task card level and clamps missing or offscreen targets to the viewport', () => {
    const context = vm.createContext({});
    vm.runInContext(source, context);
    const target = rect => context.winterFireworkTarget(rect, 1000, 800);
    assert.equal(target({left: 200, top: 220, width: 100, height: 80}).y, 260);
    assert.equal(target({left: 200, top: 220, width: 100, height: 80}).x, 250);
    assert.equal(target({left: 200, top: -300, width: 100, height: 80}).y, 60);
    assert.equal(target({left: 200, top: 1500, width: 100, height: 80}).y, 700);
    assert.ok(Number.isFinite(target(undefined).y));
});

test('celebrates while the mascot is offscreen horizontally or below the viewport, and fires toward the task', () => {
    for (const left of [-600, 1500]) {
        const page = scene(false, {roller: {left, right: left + 200}, pack: {top: 1800},
            cards: [{dataset: {taskName: 'one'}, getBoundingClientRect: () => ({left: 100, top: 200, width: 100, height: 100})}]});
        page.changed();
        let fired = false;
        let reached = false;
        for (let time = 1000; time < 30000; time += 50) {
            page.advance(time);
            if (page.world.dataset.winterCelebration === 'leaving') {
                assert.equal(page.facing.style.transform.includes('scaleX(-1)'), left < 0);
            }
            if (page.world.dataset.winterCelebration === 'firing') {
                fired = true;
                reached ||= page.points().some(point => point.y < 270 && point.x > 50 && point.x < 250);
            }
        }
        assert.equal(fired, true);
        assert.equal(reached, true);
        assert.equal(page.world.dataset.winterCelebration, 'rolling');
        assert.equal(page.frames.size, 0);
    }
});

test('each queued task gets surrounding bursts using the card position at firing time', () => {
    let top = 100;
    const page = scene(false, {cards: [
        {dataset: {taskName: 'one'}, getBoundingClientRect: () => ({left: 100, top, width: 100, height: 100})},
        {dataset: {taskName: 'two'}, getBoundingClientRect: () => ({left: 500, top: 500, width: 100, height: 100})},
    ]});
    page.changed(['one', 'two']);
    let previous = 'rolling';
    let shot = 0;
    const centers = [];
    for (let time = 1000; time <= 40000; time += 50) {
        page.advance(time);
        const phase = page.world.dataset.winterCelebration;
        if (phase === 'firing' && previous !== phase) {
            shot++;
            // Scrolling/reordering while the mascot fetches fireworks must not leave a stale target.
            top = 260;
        }
        if (phase === 'firing' && !centers[shot - 1] && page.dots().length >= 36) {
            const dots = page.dots().slice(0, 36);
            centers[shot - 1] = {x: dots.reduce((sum, point) => sum + point.x, 0) / 36,
                y: dots.reduce((sum, point) => sum + point.y, 0) / 36};
        }
        previous = phase;
    }
    assert.equal(centers.length, 2);
    const context = vm.createContext({});
    vm.runInContext(source, context);
    for (const [index, rect] of [{left: 100, top: 260, width: 100, height: 100},
        {left: 500, top: 500, width: 100, height: 100}].entries()) {
        const targets = context.winterFireworkTargets(rect, 1000, 800);
        assert.ok(targets.some(target => Math.hypot(target.x - centers[index].x, target.y - centers[index].y) < 5),
            JSON.stringify({targets, center: centers[index]}));
    }
});


test('plants each stance foot on the snow while the body moves forward and lifts the swinging foot', () => {
    const context = vm.createContext({});
    vm.runInContext(source, context);
    const start = context.winterMascotGait(0);
    for (const distance of [5, 10, 15, 25]) {
        const pose = context.winterMascotGait(distance);
        assert.ok(Math.abs(pose.back.x + distance - start.back.x) < 1e-9);
        assert.equal(pose.back.y, 137);
    }
    assert.ok(context.winterMascotGait(48 * .8).back.y < 132);
    const rest = context.winterMascotGait(38, 0);
    assert.equal(rest.back.y, 137);
    assert.equal(rest.front.y, 137);
    assert.ok(rest.bob === 0);
    assert.ok(rest.swing === 0);
    for (let distance = 0; distance <= 144; distance++) {
        const pose = context.winterMascotGait(distance);
        assert.ok(!pose.back.path.includes('NaN') && !pose.front.path.includes('NaN'));
    }
});

test('accelerates gently, travels forward monotonically and brakes symmetrically', () => {
    const context = vm.createContext({});
    vm.runInContext(source, context);
    const travel = context.winterMascotTravel;
    assert.equal(travel(0), 0);
    assert.equal(travel(1), 1);
    assert.ok(travel(.05) < .05);
    let previous = 0;
    for (let step = 1; step <= 100; step++) {
        const position = travel(step / 100);
        assert.ok(position >= previous);
        assert.ok(Math.abs(position + travel(1 - step / 100) - 1) < 1e-9);
        previous = position;
    }
});

test('animates idle walking only while the footer is visible, and wakes celebrations outside the viewport', () => {
    const footer = {top: 600, bottom: 800};
    const page = scene(false, {footer});
    page.advance(1000);
    const first = page.backLeg.attributes.d;
    page.advance(1050);
    assert.notEqual(page.backLeg.attributes.d, first);
    assert.ok(page.frames.size > 0);
    footer.top = 1600;
    footer.bottom = 1800;
    page.window.dispatchEvent(new Event('scroll'));
    page.advance(1100);
    assert.equal(page.frames.size, 0);
    page.changed();
    page.advance(1150);
    assert.equal(page.world.dataset.winterCelebration, 'leaving');
    assert.ok(page.frames.size > 0);
});

test('rolling keeps a planted foot fixed in screen space and preserves cadence across the window wrap', () => {
    for (const wrap of [false, true]) {
        const roller = {left: wrap ? 1019 : 200};
        const page = scene(false, {footer: {top: 600, bottom: 800}, roller});
        page.advance(1000);
        for (let time = 1050; time <= 2000; time += 50) page.advance(time);
        const ankle = () => Number([...page.backLeg.attributes.d.matchAll(/L([^ ]+) /g)][1][1]);
        const before = ankle();
        const pixels = wrap ? 2 : 5;
        roller.left = wrap ? -219 : roller.left + pixels;
        page.advance(2050);
        assert.ok(Math.abs((before - ankle()) * 200 / 220 - pixels) < .01);
    }
});


test('keeps the full burst while bounding canvas paints, layout reads and settled mascot writes', () => {
    const page = scene(false, {footer: {top: 600, bottom: 800}, cards: [
        {dataset: {taskName: 'one'}, getBoundingClientRect: () => ({left: 100, top: 200, width: 100, height: 100})},
    ]});
    page.changed();
    let firingFrames = 0;
    let settledWrites;
    let fullBurst = false;
    for (let time = 1000; time <= 20000; time += 50) {
        page.advance(time);
        if (page.world.dataset.winterCelebration !== 'firing') continue;
        firingFrames++;
        assert.ok(page.paints() <= 15, `Too many paints: ${page.paints()}`);
        fullBurst ||= page.points().length >= 216 && page.circles() >= 108;
        if (firingFrames === 20) settledWrites = page.writes();
        if (firingFrames === 90) assert.equal(page.writes(), settledWrites);
    }
    assert.ok(firingFrames >= 100);
    assert.equal(fullBurst, true);
    assert.equal(page.lookups(), 1);
    assert.equal(page.blur(), 0);
    assert.ok(page.reads() <= 24, `Too many layout reads: ${page.reads()}`);
});

test('refreshes cached firework geometry immediately on scroll and resize', () => {
    let top = 100;
    const page = scene(false, {cards: [
        {dataset: {taskName: 'one'}, getBoundingClientRect: () => ({left: 100, top, width: 100, height: 100})},
    ]});
    page.changed();
    let time = 1000;
    while (page.world.dataset.winterCelebration !== 'firing') { page.advance(time); time += 50; }
    const reads = page.reads();
    top = 250;
    page.window.dispatchEvent(new Event('scroll'));
    page.advance(time);
    assert.equal(page.reads(), reads + 1);
    page.window.dispatchEvent(new Event('resize'));
    page.advance(time + 50);
    assert.equal(page.reads(), reads + 2);
    assert.equal(page.lookups(), 1);
});


test('spreads five bursts one to two card sizes away, leaving the solved card clear', () => {
    const context = vm.createContext({});
    vm.runInContext(source, context);
    const rect = {left: 450, top: 330, width: 180, height: 120};
    const center = {x: 540, y: 390};
    const targets = context.winterFireworkTargets(rect, 1280, 900);
    assert.equal(targets.length, 5);
    assert.equal(new Set(targets.map(point => `${point.x},${point.y}`)).size, 5);
    for (const point of targets) {
        const distance = Math.hypot(point.x - center.x, point.y - center.y);
        assert.ok(distance >= 180 - 1e-9 && distance <= 360 + 1e-9);
        assert.ok(point.x < rect.left - 143 || point.x > rect.left + rect.width + 143 ||
            point.y < rect.top - 179 || point.y > rect.top + rect.height + 143);
    }
    assert.ok(targets.some(point => point.x < center.x));
    assert.ok(targets.some(point => point.x > center.x));
    assert.ok(targets.some(point => point.y < center.y));
    assert.ok(targets.some(point => point.y > center.y));
});

test('keeps burst centers visible and outside the card near mobile viewport borders', () => {
    const context = vm.createContext({});
    vm.runInContext(source, context);
    for (const rect of [
        {left: 10, top: 10, width: 135, height: 120},
        {left: 245, top: 540, width: 135, height: 120},
        {left: 55, top: 350, width: 135, height: 120},
    ]) {
        const points = context.winterFireworkTargets(rect, 390, 844);
        assert.equal(new Set(points.map(point => `${point.x},${point.y}`)).size, 5);
        for (const point of points) {
            assert.ok(point.x >= 35 && point.x <= 355 && point.y >= 50 && point.y <= 794);
            assert.ok(point.x < rect.left || point.x > rect.left + rect.width ||
                point.y < rect.top || point.y > rect.top + rect.height);
            const distance = Math.hypot(point.x - rect.left - rect.width / 2, point.y - rect.top - rect.height / 2);
            assert.ok(distance >= 135 - 1e-9 && distance <= 270 + 1e-9);
        }
    }
    for (const rect of [undefined, {left: 100, top: 1600, width: 135, height: 120}]) {
        for (const point of context.winterFireworkTargets(rect, 320, 600)) {
            assert.ok(Number.isFinite(point.x) && Number.isFinite(point.y));
            assert.ok(point.x >= 0 && point.x <= 320 && point.y >= 0 && point.y <= 600);
        }
    }
});
