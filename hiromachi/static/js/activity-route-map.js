(() => {
  "use strict";

  const mapElement = document.querySelector("[data-route-mode]");
  if (!mapElement) return;

  const mode = mapElement.dataset.routeMode;
  const input = document.getElementById("route-points");
  const status = document.getElementById("route-status");
  const locationStatus = document.getElementById("route-location-status");
  const currentLocationButton = document.getElementById("route-current-location");
  const undoButton = document.getElementById("route-undo");
  const clearButton = document.getElementById("route-clear");

  const report = (message) => {
    if (status) status.textContent = message;
  };
  const reportLocation = (message) => {
    if (!locationStatus) return;
    locationStatus.textContent = message;
    locationStatus.hidden = !message;
  };

  if (typeof window.L === "undefined") {
    report("地図を読み込めませんでした。ルートなしで活動を保存できます。");
    if (currentLocationButton) currentLocationButton.hidden = true;
    return;
  }

  const parsePoints = () => {
    const value = mode === "edit" ? input?.value : mapElement.dataset.routePoints;
    if (!value) return [];
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed : [];
    } catch (_error) {
      report("保存済みのルートを読み込めませんでした。");
      return [];
    }
  };

  const points = parsePoints();
  const map = window.L.map(mapElement, { scrollWheelZoom: false }).setView(
    [36.2048, 138.2529],
    5,
  );
  window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(map);

  const line = window.L.polyline(points, {
    color: "#3f6f55",
    weight: 6,
    opacity: 0.9,
    lineCap: "round",
    lineJoin: "round",
  }).addTo(map);
  const pointLayer = window.L.layerGroup().addTo(map);
  const startIcon = window.L.divIcon({
    className: "route-start-marker",
    html: '<span aria-hidden="true"></span>',
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });

  let accuracyLayer = null;
  let locating = false;
  let locationRequestId = 0;
  let animatedPointIndex = null;

  const clearAccuracy = () => {
    if (accuracyLayer) map.removeLayer(accuracyLayer);
    accuracyLayer = null;
  };

  const updateLocationButton = () => {
    if (!currentLocationButton || mode !== "edit") return;
    currentLocationButton.hidden = points.length > 0 || locating;
    currentLocationButton.disabled = locating;
    currentLocationButton.setAttribute("aria-busy", String(locating));
  };

  const update = () => {
    line.setLatLngs(points);
    pointLayer.clearLayers();
    points.forEach((point, index) => {
      if (index === 0 && mode === "edit") {
        const marker = window.L.marker(point, {
          alt: "清掃ルートの始点。ドラッグして位置を修正できます",
          autoPan: true,
          draggable: true,
          icon: startIcon,
          keyboard: true,
          title: "始点（ドラッグして修正）",
        }).addTo(pointLayer);
        if (index === animatedPointIndex) {
          marker.getElement()?.querySelector("span")?.classList.add("route-point-added");
        }
        marker.on("dragstart", clearAccuracy);
        marker.on("dragend", (event) => {
          const position = event.target.getLatLng();
          points[0] = [
            Number(position.lat.toFixed(6)),
            Number(position.lng.toFixed(6)),
          ];
          clearAccuracy();
          reportLocation("始点を手動で修正しました。");
          update();
        });
        return;
      }
      const pointMarker = window.L.circleMarker(point, {
        radius: 5,
        color: "#294d3a",
        fillColor: "#f2c75c",
        fillOpacity: 1,
        weight: 2,
      }).addTo(pointLayer);
      if (index === animatedPointIndex) {
        pointMarker.getElement()?.classList.add("route-point-added");
      }
    });
    if (input) input.value = points.length ? JSON.stringify(points) : "";
    if (mode === "edit") {
      report(
        points.length === 0
          ? "地図をタップして2地点以上を指定してください。"
          : points.length === 1
            ? "1地点を指定しています。地図をタップして次の地点を追加してください。始点はドラッグして修正できます。"
            : `${points.length}地点を指定しています。始点はドラッグして修正できます。`,
      );
      updateLocationButton();
    }
    animatedPointIndex = null;
  };

  const finishLocationRequest = () => {
    locating = false;
    updateLocationButton();
  };

  const locationErrorMessage = (error) => {
    if (error.code === 1) {
      return "現在地の利用が許可されませんでした。地図をタップして入力してください。";
    }
    if (error.code === 2) {
      return "現在地を取得できませんでした。地図をタップして入力してください。";
    }
    if (error.code === 3) {
      return "現在地の取得が時間内に完了しませんでした。地図をタップして入力してください。";
    }
    return "現在地の取得に失敗しました。地図をタップして入力してください。";
  };

  if (points.length >= 2) {
    map.fitBounds(line.getBounds(), { padding: [24, 24], maxZoom: 17 });
  } else if (points.length === 1) {
    map.setView(points[0], 16);
  }

  if (mode === "edit") {
    currentLocationButton?.addEventListener("click", () => {
      if (points.length > 0 || locating) return;
      if (!navigator.geolocation) {
        reportLocation("このブラウザーでは現在地を取得できません。地図をタップして入力してください。");
        return;
      }

      locating = true;
      const requestId = ++locationRequestId;
      reportLocation("現在地を取得しています…");
      updateLocationButton();

      navigator.geolocation.getCurrentPosition(
        (position) => {
          if (requestId !== locationRequestId) return;
          finishLocationRequest();
          if (points.length > 0) {
            reportLocation("手動で地点が追加されたため、取得した現在地は追加しませんでした。");
            return;
          }

          const point = [
            Number(position.coords.latitude.toFixed(6)),
            Number(position.coords.longitude.toFixed(6)),
          ];
          points.push(point);
          animatedPointIndex = points.length - 1;
          clearAccuracy();
          if (Number.isFinite(position.coords.accuracy) && position.coords.accuracy > 0) {
            accuracyLayer = window.L.circle(point, {
              radius: position.coords.accuracy,
              color: "#3f6f55",
              fillColor: "#3f6f55",
              fillOpacity: 0.12,
              interactive: false,
              weight: 2,
            }).addTo(map);
            reportLocation(`現在地を始点にしました。推定誤差は約${Math.round(position.coords.accuracy)}mです。必要なら始点をドラッグしてください。`);
          } else {
            reportLocation("現在地を始点にしました。必要なら始点をドラッグしてください。");
          }
          map.setView(point, 17);
          update();
        },
        (error) => {
          if (requestId !== locationRequestId) return;
          finishLocationRequest();
          reportLocation(locationErrorMessage(error));
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
      );
    });

    map.on("click", (event) => {
      if (points.length >= 100) {
        report("ルートに指定できる地点は100件までです。");
        return;
      }
      points.push([
        Number(event.latlng.lat.toFixed(6)),
        Number(event.latlng.lng.toFixed(6)),
      ]);
      animatedPointIndex = points.length - 1;
      update();
    });
    undoButton?.addEventListener("click", () => {
      points.pop();
      if (points.length === 0) {
        clearAccuracy();
        reportLocation("");
      }
      update();
    });
    clearButton?.addEventListener("click", () => {
      locationRequestId += 1;
      locating = false;
      points.length = 0;
      clearAccuracy();
      reportLocation("");
      update();
    });
  }

  update();
})();
