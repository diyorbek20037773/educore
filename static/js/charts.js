/* EDUCORE charts (SPEC §7.4): ECharts 5 loaded lazily when a chart scrolls into view.
   Data contract (`/analitika/data/<chart>/`):
     { kind: "line"|"bar"|"hbar"|"grouped"|"heatmap"|"radar", categories: [...], series: [{name, data, color?}],
       xLabels?, yLabels?, max?, unit?, table: {columns: [...], rows: [[...]]} }
   Series colours come from the server in fixed institution order (ADR-007) and never change with filters. */
(function () {
  "use strict";

  var echartsPromise = null;
  var charts = [];

  function css(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function loadEcharts() {
    if (window.echarts) return Promise.resolve(window.echarts);
    if (!echartsPromise) {
      echartsPromise = new Promise(function (resolve, reject) {
        var script = document.createElement("script");
        var base = document.querySelector('script[src*="js/charts"]');
        script.src = base ? base.src.replace(/js\/charts[^/]*\.js.*$/, "vendor/echarts/echarts.min.js") : "/static/vendor/echarts/echarts.min.js";
        script.onload = function () { resolve(window.echarts); };
        script.onerror = reject;
        document.head.appendChild(script);
      });
    }
    return echartsPromise;
  }

  function sequential(n) {
    var dark = document.documentElement.getAttribute("data-theme") === "dark";
    return dark ? ["#1F2A44", "#34507F", "#5476B4", "#7A97CF", "#9DB4E3"].slice(0, n || 5)
                : ["#E8EEF8", "#B9C8E3", "#7D97C4", "#3D5E97", "#0B1F3A"].slice(0, n || 5);
  }

  function baseOption() {
    var ink = css("--ink-2") || "#475569";
    var grid = css("--chart-grid") || "#E5E7EB";
    return {
      textStyle: { fontFamily: "Manrope Variable, system-ui, sans-serif", color: ink },
      grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
      legend: { top: 0, icon: "roundRect", itemWidth: 10, itemHeight: 10, textStyle: { color: ink } },
      tooltip: { trigger: "axis", axisPointer: { type: "line" } },
      xAxis: { axisLine: { lineStyle: { color: grid } }, axisTick: { show: false }, axisLabel: { color: ink },
               splitLine: { show: false } },
      yAxis: { axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: ink },
               splitLine: { lineStyle: { color: grid } } },
    };
  }

  function buildOption(data) {
    var option = baseOption();
    var kind = data.kind;
    if (kind === "line") {
      option.xAxis.type = "category";
      option.xAxis.data = data.categories;
      option.yAxis.type = "value";
      option.series = data.series.map(function (s) {
        return { name: s.name, type: "line", data: s.data, smooth: false, symbolSize: 8, lineStyle: { width: 2 },
                 itemStyle: { color: s.color }, endLabel: { show: data.series.length <= 4, formatter: "{a}", color: css("--ink") },
                 emphasis: { focus: "series" } };
      });
    } else if (kind === "hbar" || kind === "bar" || kind === "grouped") {
      var horizontal = kind === "hbar";
      option.tooltip = { trigger: "item" };
      option.xAxis.type = horizontal ? "value" : "category";
      option.yAxis.type = horizontal ? "category" : "value";
      (horizontal ? option.yAxis : option.xAxis).data = data.categories;
      if (horizontal) { option.yAxis.inverse = true; option.xAxis.splitLine = { lineStyle: { color: css("--chart-grid") } }; }
      option.series = data.series.map(function (s) {
        return { name: s.name, type: "bar", data: s.data, barMaxWidth: 28,
                 itemStyle: { color: s.color || sequential(4)[3], borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0] },
                 label: { show: horizontal, position: "right", color: css("--ink") } };
      });
      if (data.series.length < 2) option.legend = { show: false };
    } else if (kind === "heatmap") {
      option.tooltip = { trigger: "item" };
      option.legend = { show: false };
      option.grid.bottom = 48;
      option.xAxis = Object.assign(option.xAxis, { type: "category", data: data.xLabels, splitArea: { show: false } });
      option.yAxis = Object.assign(option.yAxis, { type: "category", data: data.yLabels, splitLine: { show: false } });
      option.visualMap = { min: 0, max: data.max || 1, calculable: false, orient: "horizontal", left: "center", bottom: 0,
                           inRange: { color: sequential(5) }, textStyle: { color: css("--ink-2") } };
      option.series = [{ type: "heatmap", data: data.series[0].data, itemStyle: { borderColor: css("--surface"), borderWidth: 2 } }];
    } else if (kind === "radar") {
      option.tooltip = { trigger: "item" };
      var narrow = window.innerWidth < 640;
      option.radar = { indicator: data.categories.map(function (c) { return { name: c, max: 100 }; }),
                       radius: narrow ? "52%" : "65%", center: ["50%", "55%"],
                       splitLine: { lineStyle: { color: css("--chart-grid") } },
                       axisName: { color: css("--ink-2"), fontSize: narrow ? 10 : 12, width: narrow ? 70 : 110, overflow: "break" } };
      option.legend = { top: 0, icon: "roundRect", itemWidth: 10, itemHeight: 10, textStyle: { color: css("--ink-2") } };
      option.series = [{ type: "radar", data: data.series.map(function (s) {
        return { name: s.name, value: s.data, itemStyle: { color: s.color }, lineStyle: { width: 2 } };
      }) }];
      delete option.xAxis; delete option.yAxis; delete option.grid;
    }
    return option;
  }

  function renderTable(card, data) {
    var box = card.querySelector(".chart-table");
    if (!box || !data.table) return;
    var table = document.createElement("table");
    table.className = "data-table";
    var head = table.createTHead().insertRow();
    data.table.columns.forEach(function (c, i) {
      var th = document.createElement("th");
      th.scope = "col";
      th.textContent = c;
      if (i > 0) th.className = "num";
      head.appendChild(th);
    });
    var body = table.createTBody();
    data.table.rows.forEach(function (row) {
      var tr = body.insertRow();
      row.forEach(function (cell, i) {
        var td = tr.insertCell();
        td.textContent = cell === null ? "—" : String(cell);
        if (i > 0) td.className = "num";
      });
    });
    box.replaceChildren(table);
  }

  function hasData(data) {
    return (data.series || []).some(function (s) {
      return (s.data || []).some(function (v) {
        var value = Array.isArray(v) ? v[v.length - 1] : (v && typeof v === "object" ? v.value : v);
        return value !== null && value !== undefined && Number(value) !== 0;
      });
    });
  }

  function draw(card) {
    var canvas = card.querySelector(".chart-canvas");
    var url = card.getAttribute("data-url");
    Promise.all([loadEcharts(), fetch(url, { headers: { Accept: "application/json" } }).then(function (r) { return r.json(); })])
      .then(function (result) {
        var echarts = result[0];
        var data = result[1];
        canvas.replaceChildren();
        renderTable(card, data);
        if (!hasData(data)) {
          canvas.classList.add("chart-empty");
          canvas.textContent = card.getAttribute("data-empty") || "—";
          return;
        }
        var chart = echarts.init(canvas, null, { renderer: "svg" });
        chart.setOption(buildOption(data));
        charts.push({ chart: chart, data: data });
      })
      .catch(function () {
        canvas.textContent = canvas.getAttribute("aria-label") + " — maʼlumot yuklanmadi.";
      });
  }

  function init() {
    // Only cards not seen yet: HTMX swaps (live panel polling, boosted navigation) call init again.
    var cards = document.querySelectorAll("[data-chart]:not([data-chart-bound])");
    if (!cards.length) return;
    charts = charts.filter(function (item) { return document.body.contains(item.chart.getDom()); });
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          observer.unobserve(entry.target);
          draw(entry.target);
        }
      });
    }, { rootMargin: "200px" });
    cards.forEach(function (card) {
      card.setAttribute("data-chart-bound", "1");
      observer.observe(card);
    });
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-chart-toggle]");
    if (!button) return;
    var card = button.closest("[data-chart]");
    var table = card.querySelector(".chart-table");
    var canvas = card.querySelector(".chart-canvas");
    var showTable = table.classList.contains("hidden");
    table.classList.toggle("hidden", !showTable);
    canvas.classList.toggle("hidden", showTable);
    button.setAttribute("aria-pressed", showTable ? "true" : "false");
  });

  document.addEventListener("educore:theme", function () {
    charts.forEach(function (item) { item.chart.setOption(buildOption(item.data), true); });
  });
  window.addEventListener("resize", function () { charts.forEach(function (item) { item.chart.resize(); }); });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
  document.addEventListener("htmx:afterSettle", init);
})();
