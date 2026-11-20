const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const {test} = require('node:test');
const vm = require('node:vm');

const source = readFileSync(path.join(__dirname, '../../manytask/static/js/new-year.js'), 'utf8');

function load({saved = null, reduced = false, blocked = false, canvasAvailable = true, graphPoints = null, random = .18} = {}) {
    function element() {
        const node = new EventTarget();
        node.attributes = {};
        node.dataset = {};
        node.style = new Map();
        node.style.setProperty = node.style.set.bind(node.style);
        node.style.removeProperty = node.style.delete.bind(node.style);
        const classes = new Set();
        node.classList = {
            add: name => classes.add(name),
            remove: (...names) => names.forEach(name => classes.delete(name)),
            toggle(name, force) { if (force) classes.add(name); else classes.delete(name); },
            contains: name => classes.has(name),
        };
        node.setAttribute = (key, value) => { node.attributes[key] = value; };
        node.getAttribute = key => node.attributes[key];
        node.getBoundingClientRect = () => ({top: 150, bottom: 250, left: 20, right: 200, width: 180, height: 100});
        node.querySelector = () => null;
        node.append = cap => { node.cap = cap; };
        node.remove = () => { node.removed = true; };
        return node;
    }
    const root = element();
    root.clientWidth = 1000;
    const toggle = element();
    const status = {};
    toggle.querySelector = () => status;
    const canvas = element();
    const drawn = [];
    canvas.getContext = () => canvasAvailable ? {
        setTransform() {}, clearRect() { drawn.length = 0; },
        beginPath() {}, fill() {}, arc(x, y) { drawn.push({x, y}); },
    } : null;
    const footer = element();
    const world = element();
    world.querySelector = selector => selector === 'canvas' ? canvas : footer;
    const plank = element();
    plank.dataset.winterDeadline = (Date.now() + 3600000) / 1000;
    if (graphPoints) {
        plank.querySelector = () => ({dataset: {points: JSON.stringify(graphPoints)}});
    }
    const document = Object.assign(new EventTarget(), {
        documentElement: root,
        body: element(),
        hidden: false,
        getElementById: id => id === 'new-year-world' ? world : null,
        querySelectorAll: selector => selector === '[data-new-year-toggle]' ? [toggle] : [plank],
        createElement: element,
    });
    const motion = Object.assign(new EventTarget(), {matches: reduced});
    const window = Object.assign(new EventTarget(), {matchMedia: () => motion, innerHeight: 800});
    const frames = new Map();
    let nextFrame = 0;
    class Observer { observe() {} disconnect() {} }
    const context = vm.createContext({
        document, window, Date, MutationObserver: Observer, ResizeObserver: Observer,
        Math: Object.assign(Object.create(Math), {random: () => random}),
        getComputedStyle: () => ({borderTopLeftRadius: '20px', borderTopWidth: '2px'}),
        localStorage: {
            getItem() { if (blocked) throw Error('blocked'); return saved; },
            setItem(key, value) { if (blocked) throw Error('blocked'); saved = value; },
        },
        requestAnimationFrame(callback) { frames.set(++nextFrame, callback); return nextFrame; },
        cancelAnimationFrame(id) { frames.delete(id); },
    });
    vm.runInContext(source, context);
    function advance(time) {
        const [id, callback] = frames.entries().next().value;
        frames.delete(id);
        callback(time);
        return drawn.map(point => ({...point}));
    }
    return {context, document, window, motion, root, toggle, status, world, plank, footer, frames, advance, saved: () => saved};
}

test('New Year mode starts enabled, disables completely, and remembers the choice on reload', () => {
    const page = load();
    assert.equal(page.world.hidden, false);
    assert.equal(page.toggle.getAttribute('aria-pressed'), 'true');
    assert.equal(page.status.textContent, 'On');
    assert.equal(page.frames.size, 1);
    const cap = page.plank.cap;
    page.toggle.dispatchEvent(new Event('click'));
    assert.equal(page.world.hidden, true);
    assert.equal(page.root.getAttribute('data-new-year'), 'off');
    assert.equal(page.toggle.getAttribute('aria-pressed'), 'false');
    assert.equal(page.status.textContent, 'Off');
    assert.equal(page.frames.size, 0);
    assert.equal(cap.removed, true);
    assert.equal(page.plank.classList.contains('winter-surface'), false);
    const reloaded = load({saved: page.saved()});
    assert.equal(reloaded.world.hidden, true);
    assert.equal(reloaded.frames.size, 0);
    reloaded.toggle.dispatchEvent(new Event('click'));
    assert.equal(reloaded.world.hidden, false);
    assert.equal(reloaded.frames.size, 1);
});

test('blocked storage and unavailable canvas preserve the toggle and static decoration', () => {
    for (const canvasAvailable of [true, false]) {
        const page = load({blocked: true, canvasAvailable});
        assert.equal(page.world.hidden, false);
        assert.ok(page.plank.cap);
        page.toggle.dispatchEvent(new Event('click'));
        assert.equal(page.world.hidden, true);
    }
});

test('reduced motion renders settled snow and icicles without scheduling animation', () => {
    const page = load({reduced: true});
    assert.equal(page.frames.size, 0);
    assert.equal(page.world.hidden, false);
    assert.equal(page.plank.cap.style.get('--snow-depth'), '7px');
    assert.equal(page.plank.cap.style.get('--ice-depth'), '12px');
    page.motion.matches = false;
    page.motion.dispatchEvent(new Event('change'));
    assert.equal(page.frames.size, 1);
    page.motion.matches = true;
    page.motion.dispatchEvent(new Event('change'));
    assert.equal(page.frames.size, 0);
});

test('hidden pages pause and resume once; storage events synchronize other tabs', () => {
    const page = load();
    page.document.hidden = true;
    page.document.dispatchEvent(new Event('visibilitychange'));
    assert.equal(page.frames.size, 0);
    page.document.hidden = false;
    page.document.dispatchEvent(new Event('visibilitychange'));
    page.document.dispatchEvent(new Event('visibilitychange'));
    assert.equal(page.frames.size, 1);
    const event = Object.assign(new Event('storage'), {key: 'manytask-new-year', newValue: 'off'});
    page.window.dispatchEvent(event);
    assert.equal(page.world.hidden, true);
    assert.equal(page.frames.size, 0);
});

test('only future deadlines less than 24 hours away melt', () => {
    const {winterIsUrgent} = load({saved: 'off'}).context;
    const now = Date.now();
    for (const delta of [-1000, 0, 86400000, 86400001]) {
        assert.equal(winterIsUrgent((now + delta) / 1000, now), false);
    }
    assert.equal(winterIsUrgent((now + 1000) / 1000, now), true);
    assert.equal(winterIsUrgent('invalid', now), false);
    assert.equal(winterIsUrgent(undefined, now), false);
});

test('interpolated deadlines use the next future graph breakpoint, skipping expired points', () => {
    const now = Date.now() / 1000;
    const urgent = load({reduced: true, graphPoints: [{ts: now - 100}, {ts: now + 3600}, {ts: now + 172800}]});
    assert.equal(urgent.plank.cap.style.get('--ice-depth'), '12px');
    const distant = load({reduced: true, graphPoints: [{ts: now - 100}, {ts: now + 172800}]});
    assert.equal(distant.plank.cap.style.get('--ice-depth'), '0px');
    const expired = load({reduced: true, graphPoints: [{ts: now - 100}]});
    assert.equal(expired.plank.cap.style.get('--ice-depth'), '0px');
});

test('foreground flakes keep falling through a plank without disappearing or recycling', () => {
    const page = load();
    let previous = page.advance(1000);
    assert.ok(previous[0].x > 20 && previous[0].x < 200);
    assert.ok(previous[0].y < 150);
    for (let time = 1050; time <= 1500; time += 50) {
        const current = page.advance(time);
        assert.equal(current.length, previous.length);
        assert.ok(current[0].y > previous[0].y);
        previous = current;
    }
    assert.ok(previous[0].y > 150);
});

test('snow accumulates on planks and the ground even when no flakes cross the plank', () => {
    const page = load({random: .8});
    page.plank.dataset.winterDeadline = (Date.now() + 172800000) / 1000;
    page.advance(1000);
    const before = Number.parseFloat(page.plank.cap.style.get('--snow-depth'));
    const groundBefore = Number.parseFloat(page.footer.style.get('--winter-ground'));
    let flakes;
    for (let time = 1050; time <= 2050; time += 50) flakes = page.advance(time);
    assert.ok(flakes.every(flake => flake.x > 200));
    assert.ok(Number.parseFloat(page.plank.cap.style.get('--snow-depth')) > before);
    assert.ok(Number.parseFloat(page.footer.style.get('--winter-ground')) > groundBefore);
});

test('cold snow builds up to a cap; urgent snow melts into bounded icicles', () => {
    const {winterSnowState} = load({saved: 'off'}).context;
    assert.equal(winterSnowState(2, 0, false, 1, 2).snow, 4);
    assert.equal(winterSnowState(8, 0, false, 1, 5).snow, 9);
    const melting = winterSnowState(8, 0, true, 3);
    assert.ok(melting.snow < 8);
    assert.ok(melting.ice > 0);
    assert.equal(winterSnowState(9, 16, true, 100).ice, 17);
    assert.equal(winterSnowState(2, 10, false, 20).ice, 0);
    assert.equal(winterSnowState(2, 0, true, 20).snow, 0);
});

test('snow follows rounded plank corners and supports localized drifts', () => {
    const {winterSnowEdge, winterDepositSnow} = load({saved: 'off'}).context;
    const depths = Array(17).fill(2);
    const deposited = winterDepositSnow(depths, .25, 3);
    assert.equal(deposited[4], 5);
    assert.ok(deposited[12] - 2 < .001);
    assert.deepEqual(depths, Array(17).fill(2));
    const edge = winterSnowEdge(180, 20, deposited, 0);
    assert.equal(edge.base, 20);
    assert.equal(edge.top, edge.base);
    const corner = winterSnowEdge(180, 20, deposited, 5);
    assert.ok(corner.top > 0, 'snow follows the curved corner below the flat top');
    const flat = winterSnowEdge(180, 20, deposited, 45);
    assert.equal(flat.base, 0);
    assert.equal(flat.top, -5);
});
