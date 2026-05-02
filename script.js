(() => {
  initMobileNav();
  initRevealAnimations();
  initCounterAnimations();
  initConstellation();
  initEarlyAccessForm();

  function initMobileNav() {
    const button = document.querySelector(".menu-toggle");
    const links = document.querySelector(".nav-links");
    if (!button || !links) return;

    button.addEventListener("click", () => {
      const isOpen = links.classList.toggle("open");
      button.setAttribute("aria-expanded", String(isOpen));
    });

    links.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => {
        links.classList.remove("open");
        button.setAttribute("aria-expanded", "false");
      });
    });
  }

  function initRevealAnimations() {
    const revealItems = document.querySelectorAll(".reveal");
    if (!revealItems.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.18, rootMargin: "0px 0px -8% 0px" }
    );

    revealItems.forEach((item, idx) => {
      item.style.transitionDelay = `${Math.min(idx * 40, 280)}ms`;
      observer.observe(item);
    });
  }

  function initCounterAnimations() {
    const values = document.querySelectorAll(".stat-value");
    if (!values.length) return;

    const runCounter = (el) => {
      const target = Number(el.dataset.target || 0);
      const suffix = el.dataset.suffix || "";
      const prefix = el.dataset.prefix || "";
      const duration = 1600;
      const start = performance.now();
      const decimalPlaces = target % 1 === 0 ? 0 : 1;

      const tick = (now) => {
        const progress = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = target * eased;
        const shown = decimalPlaces ? current.toFixed(decimalPlaces) : Math.floor(current).toLocaleString();
        el.textContent = `${prefix}${shown}${suffix}`;
        if (progress < 1) {
          requestAnimationFrame(tick);
        }
      };

      requestAnimationFrame(tick);
    };

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            values.forEach(runCounter);
            observer.disconnect();
          }
        });
      },
      { threshold: 0.45 }
    );

    const statsBar = document.getElementById("statsBar");
    if (statsBar) observer.observe(statsBar);
  }

  function initConstellation() {
    const canvas = document.getElementById("constellationCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const LINK_DISTANCE = 118;
    const CELL = LINK_DISTANCE;
    const REPULSION_RADIUS = 130;
    const REPULSION_STRENGTH = 0.055;
    const mouse = { x: -9999, y: -9999 };
    const nodes = [];
    let width = 0;
    let height = 0;
    let dpr = 1;

    function nodeCountForViewport() {
      const area = width * height;
      const density = Math.floor(area / 1150);
      return Math.min(520, Math.max(260, density));
    }

    function cellKey(x, y) {
      return `${Math.floor(x / CELL)},${Math.floor(y / CELL)}`;
    }

    const setCanvasSize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = Math.max(window.innerHeight, 480);
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const initNodes = () => {
      const n = nodeCountForViewport();
      nodes.length = 0;
      for (let i = 0; i < n; i += 1) {
        nodes.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.32,
          vy: (Math.random() - 0.5) * 0.32,
          radius: Math.random() * 1.35 + 1.15,
          pulse: Math.random() * Math.PI * 2
        });
      }
    };

    const drawEdgesSpatial = () => {
      const buckets = new Map();
      for (let i = 0; i < nodes.length; i += 1) {
        const n = nodes[i];
        const k = cellKey(n.x, n.y);
        if (!buckets.has(k)) buckets.set(k, []);
        buckets.get(k).push(i);
      }

      const offsets = [-1, 0, 1];
      for (let i = 0; i < nodes.length; i += 1) {
        const a = nodes[i];
        const cx = Math.floor(a.x / CELL);
        const cy = Math.floor(a.y / CELL);
        for (const ox of offsets) {
          for (const oy of offsets) {
            const key = `${cx + ox},${cy + oy}`;
            const bucket = buckets.get(key);
            if (!bucket) continue;
            for (const j of bucket) {
              if (j <= i) continue;
              const b = nodes[j];
              const dx = a.x - b.x;
              const dy = a.y - b.y;
              const dist = Math.hypot(dx, dy);
              if (dist < LINK_DISTANCE) {
                const alpha = (1 - dist / LINK_DISTANCE) * 0.38;
                ctx.strokeStyle = `rgba(72, 126, 255, ${alpha})`;
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(a.x, a.y);
                ctx.lineTo(b.x, b.y);
                ctx.stroke();
              }
            }
          }
        }
      }
    };

    const drawFrame = () => {
      if (width < 2 || height < 2) {
        requestAnimationFrame(drawFrame);
        return;
      }
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "rgba(5, 10, 18, 0.72)";
      ctx.fillRect(0, 0, width, height);

      drawEdgesSpatial();

      nodes.forEach((node) => {
        const dx = node.x - mouse.x;
        const dy = node.y - mouse.y;
        const dist = Math.hypot(dx, dy);
        if (dist < REPULSION_RADIUS) {
          const force = (1 - dist / REPULSION_RADIUS) * REPULSION_STRENGTH;
          node.vx += (dx / (dist || 1)) * force;
          node.vy += (dy / (dist || 1)) * force;
        }

        node.vx *= 0.992;
        node.vy *= 0.992;
        node.x += node.vx;
        node.y += node.vy;
        node.pulse += 0.026;

        if (node.x <= 0 || node.x >= width) node.vx *= -1;
        if (node.y <= 0 || node.y >= height) node.vy *= -1;
        node.x = Math.max(2, Math.min(width - 2, node.x));
        node.y = Math.max(2, Math.min(height - 2, node.y));

        const pulseSize = node.radius + Math.sin(node.pulse) * 0.65;
        ctx.beginPath();
        ctx.fillStyle = "rgba(220, 235, 255, 0.98)";
        ctx.arc(node.x, node.y, pulseSize, 0, Math.PI * 2);
        ctx.fill();

        ctx.beginPath();
        ctx.fillStyle = "rgba(46, 123, 255, 0.28)";
        ctx.arc(node.x, node.y, pulseSize * 2.5, 0, Math.PI * 2);
        ctx.fill();
      });

      requestAnimationFrame(drawFrame);
    };

    const onPointer = (clientX, clientY) => {
      mouse.x = clientX;
      mouse.y = clientY;
    };

    window.addEventListener("mousemove", (event) => {
      onPointer(event.clientX, event.clientY);
    });

    window.addEventListener("mouseleave", () => {
      mouse.x = -9999;
      mouse.y = -9999;
    });

    window.addEventListener(
      "touchstart",
      (e) => {
        if (e.touches.length) onPointer(e.touches[0].clientX, e.touches[0].clientY);
      },
      { passive: true }
    );

    window.addEventListener(
      "touchmove",
      (e) => {
        if (e.touches.length) onPointer(e.touches[0].clientX, e.touches[0].clientY);
      },
      { passive: true }
    );

    window.addEventListener("touchend", () => {
      mouse.x = -9999;
      mouse.y = -9999;
    });

    window.addEventListener("resize", () => {
      setCanvasSize();
      initNodes();
    });

    const boot = () => {
      setCanvasSize();
      initNodes();
      requestAnimationFrame(() => {
        setCanvasSize();
        initNodes();
        requestAnimationFrame(drawFrame);
      });
    };

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", boot);
    } else {
      boot();
    }
  }

  function initEarlyAccessForm() {
    const form = document.querySelector(".cta-form");
    if (!form) return;

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const thanksRaw = form.getAttribute("data-thanks-url") || "";
      const btn = form.querySelector('button[type="submit"]');
      const prevLabel = btn ? btn.textContent : "";

      if (btn) {
        btn.disabled = true;
        btn.textContent = "Sending…";
      }

      const emailEncoded = encodeURIComponent("sepehrkhavari13@gmail.com");
      const ajaxUrl = `https://formsubmit.co/ajax/${emailEncoded}`;

      const fd = new FormData(form);

      try {
        const res = await fetch(ajaxUrl, {
          method: "POST",
          body: fd,
          headers: { Accept: "application/json" }
        });

        let payload = {};
        try {
          payload = await res.json();
        } catch {
          payload = {};
        }

        if (!res.ok) {
          throw new Error(payload.message || payload.error || `HTTP ${res.status}`);
        }
        if (payload.success === false || payload.success === "false") {
          throw new Error(payload.message || "Submission rejected");
        }

        const dest = thanksRaw.trim();
        window.location.assign(dest || `${window.location.pathname}?thanks=1`);
      } catch (err) {
        console.error(err);
        if (btn) {
          btn.disabled = false;
          btn.textContent = prevLabel;
        }
        window.alert(
          "We couldn’t submit that from this page. Please try again or email hello@patentis.ai."
        );
      }
    });
  }
})();
