/* One celebration per changed task. A queued celebration starts only after
 * the mascot reaches the ball and has resumed rolling. */
function createWinterCelebrationQueue({canStart = () => true, onStart = () => ({})} = {}) {
    const phases = ['leaving', 'fetching', 'returning', 'firing', 'returning-to-ball'];
    let durations;
    const tasks = [];
    const queue = {
        phase: 'rolling', elapsed: 0, activeTask: null, completed: 0, cooldown: 0,
        get pending() { return tasks.length; },
        get progress() { return this.phase === 'rolling' ? 0 : Math.min(1, this.elapsed / durations[this.phase]); },
        enqueue(names) { if (Array.isArray(names)) tasks.push(...names.filter(name => typeof name === 'string')); },
        reset() {
            this.phase = 'rolling';
            this.activeTask = null;
            this.elapsed = this.cooldown = this.completed = tasks.length = 0;
        },
        step(seconds) {
            if (this.phase === 'rolling') {
                this.cooldown = Math.max(0, this.cooldown - seconds);
                if (!this.pending || this.cooldown > 0 || !canStart()) return;
                this.activeTask = tasks.shift();
                durations = {leaving: 2, fetching: .45, returning: 2, firing: 5.5, 'returning-to-ball': 1,
                    ...onStart(this.activeTask)};
                this.phase = 'leaving';
                this.elapsed = 0;
                return;
            }
            this.elapsed += seconds;
            if (this.elapsed < durations[this.phase]) return;
            const next = phases[phases.indexOf(this.phase) + 1];
            this.elapsed = 0;
            if (next) this.phase = next;
            else {
                this.phase = 'rolling';
                this.activeTask = null;
                this.completed++;
                this.cooldown = .4;
            }
        },
    };
    return queue;
}

// A planted foot moves backward by exactly the distance the body travels.
// The other foot lifts and swings forward, with both feet grounded at rest.
function winterMascotGait(distance, energy = 1, pushing = false) {
    const cycle = ((distance / 48) % 1 + 1) % 1;
    const bob = -.7 * (1 - Math.cos(cycle * Math.PI * 4)) * energy;
    const leg = (hip, offset, rest) => {
        const phase = (cycle + offset) % 1;
        const swing = Math.max(0, (phase - .6) / .4);
        const stride = phase < .6 ? 14.4 - phase * 48 : -14.4 + 28.8 * (.5 - .5 * Math.cos(swing * Math.PI));
        const x = hip + rest * (1 - energy) + stride * energy;
        const y = 137 - Math.sin(swing * Math.PI) * 7 * energy;
        const hipY = 114 + bob;
        const dx = x - hip;
        const dy = y - 3 - hipY;
        const length = Math.hypot(dx, dy);
        const bend = Math.sqrt(Math.max(0, 14 ** 2 - (length / 2) ** 2));
        const kneeX = hip + dx / 2 + dy / length * bend;
        const kneeY = hipY + dy / 2 - dx / length * bend;
        const path = `M${hip} ${hipY}L${kneeX} ${kneeY}L${x} ${y - 3}L${x + 9} ${y}`;
        return {path, x, y};
    };
    return {back: leg(64, 0, -8), front: leg(89, .5, 8), bob,
        lean: (pushing ? 4 : .8 * Math.sin(cycle * Math.PI * 2)) * energy,
        swing: Math.sin(cycle * Math.PI * 2) * 18 * energy};
}

// Brief acceleration and braking, with a steady pace between them.
function winterMascotTravel(progress) {
    const ramp = .15;
    if (progress < ramp) return progress ** 2 / (2 * ramp * (1 - ramp));
    if (progress > 1 - ramp) return 1 - (1 - progress) ** 2 / (2 * ramp * (1 - ramp));
    return (progress - ramp / 2) / (1 - ramp);
}

// Coordinates for the walk are SVG units; fireworks use viewport pixels.
function winterMascotRoute(rect, width, edge) {
    const scale = rect.width / 220;
    const center = rect.left + 80 * scale;
    edge ??= center < width / 2 ? -1 : 1;
    const destination = edge < 0 ? -120 : width + 120;
    const exit = (edge < 0 ? Math.min(0, destination - center) : Math.max(0, destination - center)) / scale;
    const launch = width <= 700
        ? Math.max(width * .62, width - 100)
        : Math.max(70, Math.min(width - 70, center + (center < width / 2 ? 140 : -140)));
    return {scale, edge, exit, launch: (launch - center) / scale};
}

function winterFireworkTarget(rect, width, height) {
    return {
        x: Math.max(50, Math.min(width - 50, rect ? rect.left + rect.width / 2 : width / 2)),
        y: Math.max(60, Math.min(height - 100, rect ? rect.top + rect.height / 2 : height * .35)),
    };
}

function initWinterMascot(world, motion) {
    const track = world.querySelector('.winter-roller-track');
    const roller = world.querySelector('.winter-roller');
    const traveler = world.querySelector('.winter-mascot-traveler');
    const facing = world.querySelector('.winter-mascot-facing');
    const pack = world.querySelector('.winter-firework-pack');
    const canvas = world.querySelector('.winter-fireworks');
    const footer = world.querySelector('.winter-footer');
    const upper = world.querySelector('.winter-mascot-upper');
    const backLeg = world.querySelector('.winter-leg-back');
    const frontLeg = world.querySelector('.winter-leg-front');
    const nearArm = world.querySelector('.winter-arm-near');
    const farArm = world.querySelector('.winter-arm-far');
    if (!track || !roller || !traveler || !facing || !pack || !canvas) return null;
    let enabled = false;
    let frame = null;
    let lastTime = 0;
    let geometry;
    let onScreen = false;
    let rollerScale = 1;
    let lastPhase = 'rolling';
    let gaitDistance = 0;
    let gaitEnergy = 0;
    let lastTravel = 0;
    let lastRollingX = null;
    let context;
    let width = 0;
    let height = 0;
    try { context = canvas.getContext('2d'); } catch { /* The mascot can celebrate without canvas effects. */ }

    function measure(edge) {
        return winterMascotRoute(roller.getBoundingClientRect(), width, edge);
    }

    const queue = createWinterCelebrationQueue({
        canStart: () => roller.getBoundingClientRect().width > 0,
        onStart() {
            track.classList.add('winter-celebrating');
            geometry = measure();
            const seconds = distance => Math.max(.7, Math.abs(distance) * geometry.scale / 130);
            return {leaving: seconds(geometry.exit), returning: seconds(geometry.exit - geometry.launch),
                'returning-to-ball': seconds(geometry.launch)};
        },
    });

    function clear() { context?.clearRect(0, 0, width, height); }

    function surveyFooter() {
        const rect = footer?.getBoundingClientRect();
        onScreen = !rect || (rect.bottom > 0 && rect.top < window.innerHeight);
    }

    function resize() {
        width = document.documentElement.clientWidth;
        height = window.innerHeight;
        surveyFooter();
        lastRollingX = null;
        rollerScale = roller.getBoundingClientRect().width / 220 || 1;
        const ratio = Math.min(window.devicePixelRatio || 1, 2);
        canvas.width = Math.round(width * ratio);
        canvas.height = Math.round(height * ratio);
        context?.setTransform(ratio, 0, 0, ratio, 0, 0);
        if (queue.phase !== 'rolling') geometry = measure(geometry.edge);
    }

    function fireworks(seconds) {
        if (!context) return;
        const card = [...document.querySelectorAll('[data-task-name]')]
            .find(element => element.dataset.taskName === queue.activeTask);
        const target = winterFireworkTarget(card?.getBoundingClientRect(), width, height);
        const rect = pack.getBoundingClientRect();
        const origin = {
            x: Math.max(24, Math.min(width - 24, rect.left + rect.width / 2)),
            y: rect.top > target.y + 100 && rect.top < height ? rect.top : height + 24,
        };
        const colors = ['#ef476f', '#eaaa18', '#00aa95', '#397bdf', '#ef476f'];
        const flight = Math.max(.6, Math.min(1.35, (origin.y - target.y) / 650));
        for (let shot = 0; shot < 5; shot++) {
            const age = seconds - shot * .48;
            if (age < 0 || age > flight + 1.8) continue;
            const targetX = Math.max(35, Math.min(width - 35, target.x + [-30, 34, -12, 25, 0][shot]));
            const targetY = target.y + [0, -12, 10, -8, 0][shot];
            context.strokeStyle = colors[shot];
            context.fillStyle = colors[shot];
            context.shadowColor = colors[shot];
            context.shadowBlur = 8;
            context.lineWidth = 2.4;
            if (age < flight) {
                const progress = age / flight;
                const point = t => ({x: origin.x + (targetX - origin.x) * t,
                    y: origin.y + (targetY - origin.y) * (1 - (1 - t) ** 1.6)});
                const head = point(progress);
                const tail = point(Math.max(0, progress - .12));
                context.globalAlpha = .95;
                context.beginPath();
                context.moveTo(tail.x, tail.y);
                context.lineTo(head.x, head.y);
                context.stroke();
                context.beginPath();
                context.arc(head.x, head.y, 3, 0, Math.PI * 2);
                context.fill();
            } else {
                const progress = (age - flight) / 1.8;
                const expansion = 1 - (1 - progress) ** 3;
                const radius = (width <= 700 ? 95 : 135) * expansion;
                const drop = 36 * progress * progress;
                context.globalAlpha = .95 * (1 - progress) ** .7;
                for (let ray = 0; ray < 72; ray++) {
                    const angle = ray / 72 * Math.PI * 2 + shot * .3;
                    const reach = radius * (.8 + .2 * Math.sin(ray * 17 + shot) ** 2);
                    context.beginPath();
                    context.moveTo(targetX + Math.cos(angle) * reach * .8, targetY + Math.sin(angle) * reach * .8 + drop);
                    context.lineTo(targetX + Math.cos(angle) * reach, targetY + Math.sin(angle) * reach + drop);
                    context.stroke();
                    if (ray % 2 === 0) {
                        context.beginPath();
                        context.arc(targetX + Math.cos(angle) * reach * .5,
                            targetY + Math.sin(angle) * reach * .5 + drop, 1.8 * (1 - progress), 0, Math.PI * 2);
                        context.fill();
                    }
                }
            }
        }
        context.shadowBlur = 0;
        context.globalAlpha = 1;
    }

    function animateGait(seconds, travel, moving) {
        if (!upper || !backLeg || !frontLeg) return;
        const rolling = queue.phase === 'rolling';
        if (rolling) {
            const left = roller.getBoundingClientRect().left;
            if (lastRollingX !== null && seconds > 0) {
                const lap = (window.innerWidth || width) + 240;
                const distance = (left - lastRollingX + lap) % lap;
                gaitDistance += distance / rollerScale;
            }
            lastRollingX = left;
        } else {
            gaitDistance += Math.abs(travel - lastTravel);
            lastRollingX = null;
        }
        lastTravel = travel;
        gaitEnergy += ((moving && !motion.matches ? 1 : 0) - gaitEnergy) * Math.min(1, seconds * 14);
        const pose = winterMascotGait(gaitDistance, gaitEnergy, rolling);
        backLeg.setAttribute('d', pose.back.path);
        frontLeg.setAttribute('d', pose.front.path);
        upper.style.transform = `translateY(${pose.bob}px) rotate(${pose.lean}deg)`;
        if (nearArm) nearArm.style.transform = `rotate(${pose.swing}deg)`;
        if (farArm) farArm.style.transform = `rotate(${-pose.swing}deg)`;
    }

    function render(seconds = 0) {
        const phase = queue.phase;
        if (world.dataset.winterCelebration !== phase) world.dataset.winterCelebration = phase;
        track.classList.toggle('winter-celebrating', phase !== 'rolling');
        if (phase !== 'rolling' || lastPhase !== phase) clear();
        lastPhase = phase;
        if (phase === 'rolling') {
            traveler.style.transform = '';
            facing.style.transform = '';
            animateGait(seconds, 0, enabled);
        } else {
            const progress = winterMascotTravel(queue.progress);
            let x = 0;
            let direction = geometry.edge;
            if (phase === 'leaving') x = geometry.exit * progress;
            if (phase === 'fetching') x = geometry.exit;
            if (phase === 'returning') { x = geometry.exit + (geometry.launch - geometry.exit) * progress; direction = -geometry.edge; }
            if (phase === 'firing') { x = geometry.launch; direction = geometry.launch < 0 ? -1 : 1; }
            if (phase === 'returning-to-ball') { x = geometry.launch * (1 - progress); direction = geometry.launch > 0 ? -1 : 1; }
            traveler.style.transform = `translateX(${x}px)`;
            animateGait(seconds, x, !['fetching', 'firing'].includes(phase));
            facing.style.transform = direction < 0 ? 'translateX(160px) scaleX(-1)' : '';
            if (phase === 'firing') fireworks(queue.elapsed);
        }
    }

    function animate(time) {
        frame = null;
        if (!enabled || motion.matches || document.hidden) return;
        const seconds = lastTime ? Math.min((time - lastTime) / 1000, .05) : 0;
        lastTime = time;
        queue.step(seconds);
        render(seconds);
        if (onScreen || queue.pending || queue.phase !== 'rolling' || queue.cooldown) frame = requestAnimationFrame(animate);
    }

    function wake() {
        lastTime = 0;
        if (enabled && !motion.matches && !document.hidden && frame === null &&
            (onScreen || queue.pending || queue.phase !== 'rolling' || queue.cooldown)) frame = requestAnimationFrame(animate);
    }

    function reset() {
        if (frame !== null) cancelAnimationFrame(frame);
        frame = null;
        lastTime = 0;
        queue.reset();
        gaitDistance = gaitEnergy = lastTravel = 0;
        lastRollingX = null;
        render();
    }

    document.addEventListener('manytask:scores-changed', event => {
        if (!enabled || motion.matches) return;
        queue.enqueue(event.detail?.tasks);
        wake();
    });
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            if (frame !== null) cancelAnimationFrame(frame);
            frame = null;
        } else wake();
    });
    motion.addEventListener('change', () => { if (motion.matches) reset(); else wake(); });
    // Visibility only controls idle walking work; celebrations always advance offscreen.
    if (typeof IntersectionObserver !== 'undefined' && footer) {
        new IntersectionObserver(entries => { onScreen = entries[0].isIntersecting; wake(); }).observe(footer);
    } else {
        window.addEventListener('scroll', () => { surveyFooter(); wake(); }, {passive: true});
    }
    window.addEventListener('resize', () => { if (enabled) { resize(); wake(); } });
    return {setEnabled(value) { enabled = value; if (!enabled) reset(); else { resize(); render(); wake(); } }};
}
