/* Map easter egg – Mapbox GL JS route visualization */
/* Config globals (MAPBOX_ACCESS_TOKEN, MAP_DATA_URL) injected by map.html inline script */

const MAPBOX_STYLE = "mapbox://styles/mapbox/satellite-streets-v12";

if (!window.MAPBOX_ACCESS_TOKEN) {
  throw new Error(
    "Missing MAPBOX_ACCESS_TOKEN. Set environment variable and restart app.",
  );
}

mapboxgl.accessToken = window.MAPBOX_ACCESS_TOKEN;
if (typeof mapboxgl.setTelemetryEnabled === "function") {
  mapboxgl.setTelemetryEnabled(false);
}

const map = new mapboxgl.Map({
  container: "map",
  style: MAPBOX_STYLE,
  center: [0, 0],
  zoom: 2,
  pitch: 52,
});
map.addControl(new mapboxgl.NavigationControl(), "top-right");

// Load route data from external JSON
const routePoints = await fetch(window.MAP_DATA_URL)
  .then((r) => r.json())
  .catch(() => []);

const timelineList = document.getElementById("timeline-list");
routePoints.forEach((point) => {
  const item = document.createElement("li");
  item.className = "timeline-item";
  item.innerHTML = `<strong>${point.timestamp || point.title}</strong><span>${point.location}</span><span>${point.street || point.coordinates}</span>`;
  timelineList.appendChild(item);
});

const validPoints = routePoints.filter(
  (point) =>
    Number.isFinite(point.latitude) && Number.isFinite(point.longitude),
);
if (validPoints.length > 0) {
  map.on("load", () => {
    map.addSource("route", {
      type: "geojson",
      data: {
        type: "Feature",
        geometry: {
          type: "LineString",
          coordinates: validPoints.map((point) => [
            point.longitude,
            point.latitude,
          ]),
        },
        properties: {},
      },
    });

    map.addLayer({
      id: "route-line",
      type: "line",
      source: "route",
      layout: {
        "line-cap": "round",
        "line-join": "round",
      },
      paint: {
        "line-color": "#f8efe2",
        "line-width": 5,
        "line-opacity": 0.9,
      },
    });
    /*
    const carMarkerEl = document.createElement("div");
    carMarkerEl.className = "car-marker";

    carMarkerEl.innerHTML = `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M5 17h14v-5H5v5zm11.5-11H7.5l-1.5 4h13l-1.5-4z" fill="#000"/>
<circle cx="7.5" cy="17.5" r="1.5" fill="#000"/>
<circle cx="16.5" cy="17.5" r="1.5" fill="#000"/>
</svg>`;

    const carMarker = new mapboxgl.Marker({
      element: carMarkerEl,
      anchor: "center",
    })
      .setLngLat([validPoints[0].longitude, validPoints[0].latitude])
      .addTo(map);

    // Animation along route
    const animationDuration = validPoints.length > 1 ? 20000 : 0;
    let start = null;
    let animationFrameId = null;
    function interpolateLngLat(a, b, t) {
      return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
    }
    function getPositionAtPhase(phase) {
      const totalSegments = validPoints.length - 1;
      const scaled = phase * totalSegments;
      const idx = Math.floor(scaled);
      const segmentPhase = scaled - idx;
      if (idx >= totalSegments) {
        return [
          validPoints[totalSegments].longitude,
          validPoints[totalSegments].latitude,
        ];
      }
      const a = [validPoints[idx].longitude, validPoints[idx].latitude];
      const b = [
        validPoints[idx + 1].longitude,
        validPoints[idx + 1].latitude,
      ];
      return interpolateLngLat(a, b, segmentPhase);
    }
    function frame(time) {
      if (!start) start = time;
      const elapsed = time - start;
      let phase = elapsed / animationDuration;
      if (phase > 1) {
        phase = 1;
      }
      const pos = getPositionAtPhase(phase);
      carMarker.setLngLat(pos);
      if (phase >= 1) {
        // loop after pause
        setTimeout(() => {
          start = null;
          animationFrameId = requestAnimationFrame(frame);
        }, 2500);
        return;
      }
      animationFrameId = requestAnimationFrame(frame);
    }

    if (validPoints.length > 1) {
      animationFrameId = requestAnimationFrame(frame);
    }
    */

    if (routePoints.length === 1) {
      map.easeTo({
        center: [routePoints[0].longitude, routePoints[0].latitude],
        zoom: 10.5,
        essential: true,
        duration: 0,
      });
    } else {
      const bounds = new mapboxgl.LngLatBounds();
      routePoints.forEach((point) =>
        bounds.extend([point.longitude, point.latitude]),
      );
      map.fitBounds(bounds, { padding: 80, maxZoom: 11, duration: 0 });
    }
  });
}
