"use strict";

(() => {
  const previews = document.querySelectorAll("[data-route-preview]");
  const unavailable = "地図を読み込めませんでした。詳しく見るから詳細を確認できます。";

  const initialize = (preview) => {
    const element = preview.querySelector("[data-preview-map]");
    const status = preview.querySelector("[data-preview-status]");
    const reportError = () => {
      status.textContent = unavailable;
      status.hidden = false;
    };
    if (!window.L) {
      reportError();
      return;
    }
    let points;
    try {
      points = JSON.parse(preview.dataset.routePoints);
      if (!Array.isArray(points) || points.length < 1 || points.length > 100 ||
          !points.every(p => Array.isArray(p) && p.length === 2 &&
            p.every(Number.isFinite) && Math.abs(p[0]) <= 90 && Math.abs(p[1]) <= 180)) {
        reportError();
        return;
      }
    } catch (_error) {
      reportError();
      return;
    }

    const map = window.L.map(element, {
      dragging: false,
      touchZoom: false,
      scrollWheelZoom: false,
      doubleClickZoom: false,
      boxZoom: false,
      keyboard: false,
      zoomControl: false,
      fadeAnimation: false,
      zoomAnimation: false,
    });
    map.attributionControl.setPrefix(false);
    if (points.length === 1) {
      map.setView(points[0], 16);
      window.L.circleMarker(points[0], {
        radius: 7, color: "#294d3a", fillColor: "#f2c75c",
        fillOpacity: 1, weight: 2, interactive: false,
      }).addTo(map);
    } else {
      const line = window.L.polyline(points, {
        color: "#3f6f55", weight: 5, opacity: 0.95, interactive: false,
      }).addTo(map);
      map.fitBounds(line.getBounds(), { padding: [16, 16], maxZoom: 16 });
    }

    status.textContent = "地図を読み込んでいます。";
    let hasTileError = false;
    const tiles = window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    });
    tiles.on("tileerror", () => {
      hasTileError = true;
      reportError();
    });
    tiles.on("load", () => { status.hidden = !hasTileError; });
    tiles.addTo(map);
  };

  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          observer.unobserve(entry.target);
          initialize(entry.target);
        }
      });
    }, { rootMargin: "160px" });
    previews.forEach(preview => observer.observe(preview));
  } else {
    previews.forEach(initialize);
  }
})();
