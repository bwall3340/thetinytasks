'use strict';

class KoiFish {
    constructor(canvas, startOnScreen = false) {
        this.canvas = canvas;
        this.size   = 40 + Math.random() * 38;
        this.speed  = 0.018 + Math.random() * 0.016;
        this.angle  = Math.random() * Math.PI * 2;
        this.steer  = (Math.random() - 0.5) * 0.00065;
        this.tailPhase = Math.random() * Math.PI * 2;
        this.scheme = KoiFish.SCHEMES[Math.floor(Math.random() * KoiFish.SCHEMES.length)];

        if (startOnScreen) {
            this.x = canvas.width  * (0.08 + Math.random() * 0.84);
            this.y = canvas.height * (0.08 + Math.random() * 0.84);
        } else {
            this._spawnEdge();
        }
    }

    _spawnEdge() {
        const { width: w, height: h } = this.canvas;
        const pad  = this.size * 2.5;
        const side = Math.floor(Math.random() * 4);
        const arc  = 0.6;

        if (side === 0) {
            this.x = -pad;      this.y = h * 0.1 + Math.random() * h * 0.8;
            this.angle = (Math.random() - 0.5) * arc;
        } else if (side === 1) {
            this.x = w + pad;   this.y = h * 0.1 + Math.random() * h * 0.8;
            this.angle = Math.PI + (Math.random() - 0.5) * arc;
        } else if (side === 2) {
            this.x = w * 0.1 + Math.random() * w * 0.8;  this.y = -pad;
            this.angle = Math.PI / 2 + (Math.random() - 0.5) * arc;
        } else {
            this.x = w * 0.1 + Math.random() * w * 0.8;  this.y = h + pad;
            this.angle = -Math.PI / 2 + (Math.random() - 0.5) * arc;
        }
    }

    _offScreen() {
        const pad = this.size * 3;
        return (
            this.x < -pad || this.x > this.canvas.width  + pad ||
            this.y < -pad || this.y > this.canvas.height + pad
        );
    }

    update(dt, boost) {
        this.angle += this.steer * dt;
        if (Math.random() < 0.0012 * dt) {
            this.steer = (Math.random() - 0.5) * 0.00065;
        }
        const spd = this.speed * boost;
        this.x += Math.cos(this.angle) * spd * dt;
        this.y += Math.sin(this.angle) * spd * dt;
        this.tailPhase += 0.0042 * dt * Math.max(0.7, boost * 0.55);
        if (this._offScreen()) this._spawnEdge();
    }

    draw(ctx) {
        const s  = this.size;
        const tw = Math.sin(this.tailPhase) * 0.38;
        const { body, accent, spot } = this.scheme;
        const rgba = KoiFish._rgba;

        ctx.save();
        ctx.translate(this.x, this.y);
        ctx.rotate(this.angle);

        // ── TAIL ──────────────────────────────────────────────────
        ctx.save();
        ctx.rotate(tw * 0.62);

        // upper lobe
        ctx.beginPath();
        ctx.moveTo(-s * 0.36, -s * 0.03);
        ctx.bezierCurveTo(-s * 0.54, -s * 0.11, -s * 0.95, -s * 0.38, -s * 0.82, -s * 0.06);
        ctx.bezierCurveTo(-s * 0.72, -s * 0.01, -s * 0.54, -s * 0.01, -s * 0.36, -s * 0.03);
        ctx.fillStyle = rgba(body, 0.48);
        ctx.fill();

        // lower lobe (mirror)
        ctx.beginPath();
        ctx.moveTo(-s * 0.36,  s * 0.03);
        ctx.bezierCurveTo(-s * 0.54,  s * 0.11, -s * 0.95,  s * 0.38, -s * 0.82,  s * 0.06);
        ctx.bezierCurveTo(-s * 0.72,  s * 0.01, -s * 0.54,  s * 0.01, -s * 0.36,  s * 0.03);
        ctx.fillStyle = rgba(body, 0.48);
        ctx.fill();

        ctx.restore();

        // ── BODY ──────────────────────────────────────────────────
        ctx.beginPath();
        ctx.moveTo( s * 0.48,  0);
        ctx.bezierCurveTo( s * 0.48, -s * 0.21,  s * 0.01, -s * 0.27, -s * 0.35, -s * 0.15);
        ctx.bezierCurveTo(-s * 0.46, -s * 0.09, -s * 0.46,  s * 0.09, -s * 0.35,  s * 0.15);
        ctx.bezierCurveTo( s * 0.01,  s * 0.27,  s * 0.48,  s * 0.21,  s * 0.48,  0);
        ctx.fillStyle = rgba(body, 0.74);
        ctx.fill();

        // ── COLOUR PATCHES (clipped to body) ──────────────────────
        ctx.save();
        ctx.beginPath();
        ctx.moveTo( s * 0.48,  0);
        ctx.bezierCurveTo( s * 0.48, -s * 0.21,  s * 0.01, -s * 0.27, -s * 0.35, -s * 0.15);
        ctx.bezierCurveTo(-s * 0.46, -s * 0.09, -s * 0.46,  s * 0.09, -s * 0.35,  s * 0.15);
        ctx.bezierCurveTo( s * 0.01,  s * 0.27,  s * 0.48,  s * 0.21,  s * 0.48,  0);
        ctx.clip();

        ctx.beginPath();
        ctx.ellipse(s * 0.1, -s * 0.08, s * 0.19, s * 0.13, 0.4, 0, Math.PI * 2);
        ctx.fillStyle = rgba(accent, 0.66);
        ctx.fill();

        ctx.beginPath();
        ctx.ellipse(-s * 0.14, s * 0.07, s * 0.15, s * 0.11, -0.35, 0, Math.PI * 2);
        ctx.fillStyle = rgba(spot, 0.56);
        ctx.fill();
        ctx.restore();

        // ── DORSAL FIN ────────────────────────────────────────────
        ctx.beginPath();
        ctx.moveTo( s * 0.21, -s * 0.16);
        ctx.bezierCurveTo( s * 0.1, -s * 0.44, -s * 0.1, -s * 0.38, -s * 0.19, -s * 0.15);
        ctx.closePath();
        ctx.fillStyle = rgba(accent, 0.36);
        ctx.fill();

        // ── PECTORAL FINS ─────────────────────────────────────────
        for (const sign of [1, -1]) {
            ctx.save();
            ctx.rotate(sign * tw * 0.28);
            ctx.beginPath();
            ctx.moveTo( s * 0.1, sign * s * 0.16);
            ctx.bezierCurveTo(s * 0.24, sign * s * 0.38, -s * 0.08, sign * s * 0.42, -s * 0.1, sign * s * 0.18);
            ctx.closePath();
            ctx.fillStyle = rgba(body, 0.40);
            ctx.fill();
            ctx.restore();
        }

        // ── EYE ───────────────────────────────────────────────────
        ctx.beginPath();
        ctx.arc(s * 0.30, -s * 0.07, s * 0.055, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(18,12,5,0.88)';
        ctx.fill();

        ctx.beginPath();
        ctx.arc(s * 0.285, -s * 0.088, s * 0.02, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255,255,255,0.55)';
        ctx.fill();

        ctx.restore();
    }

    static _rgba([r, g, b], a) {
        return `rgba(${r},${g},${b},${a})`;
    }
}

KoiFish.SCHEMES = [
    { body: [232, 108, 52],  accent: [248, 240, 220], spot: [195,  42,  30] },
    { body: [244, 162, 82],  accent: [200,  48,  32], spot: [252, 240, 200] },
    { body: [250, 242, 224], accent: [210,  60,  36], spot: [238, 140,  54] },
    { body: [196,  82,  52], accent: [252, 240, 218], spot: [238, 190, 120] },
];


class KoiPond {
    constructor() {
        this.canvas     = document.getElementById('koi-canvas');
        this.ctx        = this.canvas.getContext('2d');
        this.fish       = [];
        this.boost      = 1;
        this.boostDecay = 0;
        this.ripples    = [];
        this.lastTime   = null;
        this._raf       = null;

        this._onResize();
        window.addEventListener('resize', () => this._onResize());

        const count = 7 + Math.floor(Math.random() * 3);
        for (let i = 0; i < count; i++) {
            this.fish.push(new KoiFish(this.canvas, true));
        }
    }

    _onResize() {
        this.canvas.width  = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }

    tap(clientX, clientY) {
        this.boost      = 4.2;
        this.boostDecay = 0.0022;
        // Two expanding rings for a "tapped glass" feel
        this.ripples.push({ x: clientX, y: clientY, r: 3,  alpha: 0.68 });
        this.ripples.push({ x: clientX, y: clientY, r: 14, alpha: 0.40 });
    }

    start() {
        if (this._raf) return;
        this.lastTime = performance.now();
        this._raf = requestAnimationFrame(t => this._loop(t));
    }

    stop() {
        if (this._raf) {
            cancelAnimationFrame(this._raf);
            this._raf = null;
        }
    }

    _loop(ts) {
        this._raf = requestAnimationFrame(t => this._loop(t));

        const dt = Math.min(ts - this.lastTime, 50);
        this.lastTime = ts;

        if (this.boost > 1) {
            this.boost = Math.max(1, this.boost - this.boostDecay * dt);
        }

        const ctx = this.ctx;
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        this.fish.forEach(f => { f.update(dt, this.boost); f.draw(ctx); });

        this.ripples = this.ripples.filter(rip => {
            rip.r     += dt * 0.13;
            rip.alpha -= dt * 0.003;
            if (rip.alpha <= 0) return false;
            ctx.beginPath();
            ctx.arc(rip.x, rip.y, rip.r, 0, Math.PI * 2);
            ctx.strokeStyle = `rgba(255,255,255,${rip.alpha.toFixed(3)})`;
            ctx.lineWidth = 1.5;
            ctx.stroke();
            return true;
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.koiPond = new KoiPond();

    document.getElementById('main-page').addEventListener('click', e => {
        window.koiPond.tap(e.clientX, e.clientY);
    });
});
