// Particle field animation
(function () {
  const field = document.getElementById('particles');
  if (!field) return;

  const canvas = document.createElement('canvas');
  const ctx    = canvas.getContext('2d');
  field.appendChild(canvas);

  function resize() {
    canvas.width  = field.offsetWidth;
    canvas.height = field.offsetHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  const COUNT = 60;
  const particles = Array.from({ length: COUNT }, () => ({
    x:   Math.random() * canvas.width,
    y:   Math.random() * canvas.height,
    r:   Math.random() * 1.5 + 0.4,
    vx:  (Math.random() - 0.5) * 0.3,
    vy:  (Math.random() - 0.5) * 0.15 - 0.05,
    a:   Math.random(),
  }));

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    particles.forEach(p => {
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(34,211,200,${p.a * 0.5})`;
      ctx.fill();

      p.x += p.vx;
      p.y += p.vy;
      p.a += (Math.random() - 0.5) * 0.01;
      p.a  = Math.max(0.05, Math.min(0.9, p.a));

      if (p.x < -10)             p.x = canvas.width  + 10;
      if (p.x > canvas.width+10) p.x = -10;
      if (p.y < -10)             p.y = canvas.height + 10;
      if (p.y > canvas.height+10) p.y = -10;
    });
    requestAnimationFrame(draw);
  }
  draw();
})();

// Scroll reveal
const observer = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      e.target.style.opacity    = '1';
      e.target.style.transform  = 'translateY(0)';
    }
  });
}, { threshold: 0.1 });

document.querySelectorAll('.problem-card, .step, .split-text, .split-visual').forEach(el => {
  el.style.opacity   = '0';
  el.style.transform = 'translateY(32px)';
  el.style.transition = 'opacity 0.7s ease, transform 0.7s ease';
  observer.observe(el);
});
