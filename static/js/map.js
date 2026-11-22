(function () {
  'use strict';
  if (!window.L) return;

  var map = L.map('map').setView([9.8, 45.4], 7);

  var carto = '&copy; OpenStreetMap contributors &copy; CARTO';
  var streets = L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
    maxZoom: 19, subdomains: 'abcd', attribution: carto
  }).addTo(map);
  var light = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19, subdomains: 'abcd', attribution: carto
  });
  var dark = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19, subdomains: 'abcd', attribution: carto
  });
  var imagery = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 19, attribution: 'Imagery &copy; Esri'
  });
  L.control.layers({ 'Streets': streets, 'Light': light, 'Dark': dark, 'Satellite': imagery }).addTo(map);
  L.control.scale({ metric: true, imperial: false }).addTo(map);

  var palette = ['#1e8e3e', '#1565c0', '#e8711a', '#6a3fb5', '#0f8a9d', '#c62828'];
  var active = {};
  var colorIndex = 0;

  function popupHtml(props, title, url) {
    var rows = Object.keys(props || {}).slice(0, 12).map(function (k) {
      var v = props[k] === null ? '' : String(props[k]);
      return '<tr><th>' + escapeHtml(k) + '</th><td>' + escapeHtml(v) + '</td></tr>';
    }).join('');
    return '<strong>' + escapeHtml(title) + '</strong><table class="popup-table">' + rows +
      '</table><a href="' + url + '">Dataset details &rarr;</a>';
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function addLayer(input) {
    var slug = input.dataset.slug, title = input.dataset.title, url = input.dataset.url;
    var color = palette[colorIndex++ % palette.length];

    if (input.dataset.preview) {
      fetch(input.dataset.preview).then(function (r) {
        if (!r.ok) throw new Error('Preview unavailable');
        return r.json();
      }).then(function (data) {
        if (!input.checked) return;
        var layer = L.geoJSON(data, {
          style: { color: color, weight: 2, fillOpacity: 0.2 },
          pointToLayer: function (f, ll) {
            return L.circleMarker(ll, { radius: 6, color: '#fff', weight: 1.5, fillColor: color, fillOpacity: 0.95 });
          },
          onEachFeature: function (f, l) { l.bindPopup(popupHtml(f.properties, title, url)); }
        }).addTo(map);
        active[slug] = layer;
        if (layer.getBounds().isValid()) map.fitBounds(layer.getBounds(), { padding: [30, 30], maxZoom: 12 });
      }).catch(function () { addBbox(input, color); });
    } else {
      addBbox(input, color);
    }
  }

  function addBbox(input, color) {
    if (!input.dataset.bbox) return;
    var b = input.dataset.bbox.split(',').map(Number);
    var bounds = [[b[1], b[0]], [b[3], b[2]]];
    var rect = L.rectangle(bounds, { color: color, weight: 2, dashArray: '6 4', fillOpacity: 0.05 })
      .bindPopup('<strong>' + escapeHtml(input.dataset.title) + '</strong><br>Coverage area only. <a href="' + input.dataset.url + '">Download dataset &rarr;</a>')
      .addTo(map);
    active[input.dataset.slug] = rect;
    map.fitBounds(bounds, { padding: [30, 30], maxZoom: 10 });
  }

  function removeLayer(slug) {
    if (active[slug]) { map.removeLayer(active[slug]); delete active[slug]; }
  }

  document.querySelectorAll('.layer-toggle').forEach(function (input) {
    input.addEventListener('change', function () {
      if (input.checked) addLayer(input); else removeLayer(input.dataset.slug);
    });
    if (input.checked) addLayer(input);
  });

  var filter = document.getElementById('layer-filter');
  if (filter) filter.addEventListener('input', function () {
    var q = filter.value.toLowerCase();
    document.querySelectorAll('#layer-list li[data-title]').forEach(function (li) {
      li.style.display = li.dataset.title.indexOf(q) === -1 ? 'none' : '';
    });
  });
})();
