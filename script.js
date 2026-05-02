(() => {
  const page = document.body.dataset.page || "";

  initMobileNav();
  initRevealAnimations();
  initCounterAnimations();
  if (page === "home") {
    initPatentGraph();
  }

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

  function initPatentGraph() {
    const canvas = document.getElementById("patentGraph");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const MAX_NODES = 80;
    const LINK_DISTANCE = 155;
    const REPULSION_RADIUS = 145;
    const REPULSION_STRENGTH = 0.06;
    const mouse = { x: -9999, y: -9999 };
    const nodes = [];
    let width = 0;
    let height = 0;
    let dpr = 1;

    const setCanvasSize = () => {
      dpr = window.devicePixelRatio || 1;
      width = window.innerWidth;
      height = Math.max(window.innerHeight, 620);
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const initNodes = () => {
      nodes.length = 0;
      for (let i = 0; i < MAX_NODES; i += 1) {
        nodes.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.35,
          vy: (Math.random() - 0.5) * 0.35,
          radius: Math.random() * 1.6 + 1.5,
          pulse: Math.random() * Math.PI * 2
        });
      }
    };

    const drawFrame = () => {
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "rgba(5, 10, 18, 0.8)";
      ctx.fillRect(0, 0, width, height);

      for (let i = 0; i < nodes.length; i += 1) {
        const a = nodes[i];
        for (let j = i + 1; j < nodes.length; j += 1) {
          const b = nodes[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.hypot(dx, dy);
          if (dist < LINK_DISTANCE) {
            const alpha = (1 - dist / LINK_DISTANCE) * 0.4;
            ctx.strokeStyle = `rgba(72, 126, 255, ${alpha})`;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }

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
        node.pulse += 0.028;

        if (node.x <= 0 || node.x >= width) node.vx *= -1;
        if (node.y <= 0 || node.y >= height) node.vy *= -1;
        node.x = Math.max(2, Math.min(width - 2, node.x));
        node.y = Math.max(2, Math.min(height - 2, node.y));

        const pulseSize = node.radius + Math.sin(node.pulse) * 0.7;
        ctx.beginPath();
        ctx.fillStyle = "rgba(198, 222, 255, 0.92)";
        ctx.arc(node.x, node.y, pulseSize, 0, Math.PI * 2);
        ctx.fill();

        ctx.beginPath();
        ctx.fillStyle = "rgba(46, 123, 255, 0.25)";
        ctx.arc(node.x, node.y, pulseSize * 2.6, 0, Math.PI * 2);
        ctx.fill();
      });

      requestAnimationFrame(drawFrame);
    };

    window.addEventListener("mousemove", (event) => {
      mouse.x = event.clientX;
      mouse.y = event.clientY;
    });

    window.addEventListener("mouseleave", () => {
      mouse.x = -9999;
      mouse.y = -9999;
    });

    window.addEventListener("resize", () => {
      setCanvasSize();
      initNodes();
    });

    setCanvasSize();
    initNodes();
    requestAnimationFrame(drawFrame);
  }
})();
