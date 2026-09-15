/**
 * ChartRenderer — Handles rendering interactive Bar, Line, Scatter, Pie, and KPI visualizations.
 * Built on Chart.js with responsive dark-mode styling and contract compliance.
 */
class ChartRenderer {
  constructor() {
    this.activeCharts = new Map();
  }

  render(containerId, chartSpec) {
    if (!chartSpec) return null;

    const container = document.getElementById(containerId);
    if (!container) return null;

    // Reset container
    container.innerHTML = "";

    const type = chartSpec.type || "bar";

    // 1. KPI Card
    if (type === "kpi") {
      return this._renderKPI(container, chartSpec);
    }

    // 2. Table
    if (type === "table") {
      return this._renderTable(container, chartSpec);
    }

    // Canvas-based charts (Bar, Line, Scatter, Pie)
    const canvas = document.createElement("canvas");
    canvas.id = `chart_canvas_${Date.now()}`;
    container.appendChild(canvas);

    const ctx = canvas.getContext("2d");

    if (type === "bar") {
      return this._renderBar(ctx, chartSpec);
    } else if (type === "line") {
      return this._renderLine(ctx, chartSpec);
    } else if (type === "scatter") {
      return this._renderScatter(ctx, chartSpec);
    } else if (type === "pie" || type === "doughnut") {
      return this._renderPie(ctx, chartSpec);
    }

    return null;
  }

  _renderKPI(container, spec) {
    const kpiWrap = document.createElement("div");
    kpiWrap.className = "kpi-wrapper";
    
    const formattedVal = typeof spec.value === "number" ? spec.value.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : spec.value;
    
    kpiWrap.innerHTML = `
      <div class="kpi-value">${spec.unit && spec.unit.includes("₹") ? "₹" : ""}${formattedVal}</div>
      <div class="kpi-unit">${spec.unit || ""}</div>
      <div class="kpi-title">${spec.title || ""}</div>
    `;
    container.appendChild(kpiWrap);
    return null;
  }

  _renderBar(ctx, spec) {
    const labels = (spec.data || []).map(d => d.label || d.mandi_name || d.entity || d.crop_name || Object.values(d)[0]);
    const values = (spec.data || []).map(d => d.value !== undefined ? d.value : d[spec.y] || Object.values(d)[1]);

    return new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{
          label: spec.y_label || spec.y || "Value",
          data: values,
          backgroundColor: "rgba(16, 185, 129, 0.75)",
          hoverBackgroundColor: "rgba(16, 185, 129, 0.95)",
          borderColor: "#10b981",
          borderWidth: 1.5,
          borderRadius: 6,
          maxBarThickness: 45
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            titleColor: "#f8fafc",
            bodyColor: "#10b981",
            borderColor: "rgba(255, 255, 255, 0.1)",
            borderWidth: 1,
            padding: 10,
            callbacks: {
              label: (ctx) => ` ${ctx.dataset.label}: ${Number(ctx.raw).toLocaleString("en-IN")}`
            }
          }
        },
        scales: {
          x: {
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            ticks: { color: "#94a3b8", font: { family: "Inter", size: 11 } }
          },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            ticks: {
              color: "#94a3b8",
              font: { family: "Inter", size: 11 },
              callback: (val) => Number(val).toLocaleString("en-IN")
            }
          }
        }
      }
    });
  }

  _renderLine(ctx, spec) {
    const labels = (spec.data || []).map(d => d.date);
    const values = (spec.data || []).map(d => d[spec.y] !== undefined ? d[spec.y] : d.value);

    // Gradient fill
    const gradient = ctx.createLinearGradient(0, 0, 0, 350);
    gradient.addColorStop(0, "rgba(16, 185, 129, 0.35)");
    gradient.addColorStop(1, "rgba(16, 185, 129, 0.0)");

    return new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [{
          label: spec.y_label || spec.y || "Trend",
          data: values,
          borderColor: "#10b981",
          borderWidth: 2.2,
          pointRadius: labels.length > 50 ? 0 : 3,
          pointHoverRadius: 6,
          pointBackgroundColor: "#10b981",
          backgroundColor: gradient,
          fill: true,
          tension: 0.25
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          intersect: false,
          mode: "index"
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            titleColor: "#f8fafc",
            bodyColor: "#10b981",
            borderColor: "rgba(255, 255, 255, 0.1)",
            borderWidth: 1,
            padding: 10,
            callbacks: {
              label: (ctx) => ` ${ctx.dataset.label}: ${Number(ctx.raw).toLocaleString("en-IN")}`
            }
          }
        },
        scales: {
          x: {
            grid: { color: "rgba(255, 255, 255, 0.04)" },
            ticks: {
              color: "#94a3b8",
              font: { family: "Inter", size: 10 },
              maxTicksLimit: 10
            }
          },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            ticks: {
              color: "#94a3b8",
              font: { family: "Inter", size: 11 },
              callback: (val) => Number(val).toLocaleString("en-IN")
            }
          }
        }
      }
    });
  }

  _renderScatter(ctx, spec) {
    const rawData = (spec.data || []).map(d => ({
      x: d.x,
      y: d.y,
      date: d.date
    }));

    return new Chart(ctx, {
      type: "scatter",
      data: {
        datasets: [{
          label: `${spec.x_label || spec.x} vs ${spec.y_label || spec.y}`,
          data: rawData,
          backgroundColor: "rgba(245, 158, 11, 0.65)",
          hoverBackgroundColor: "#f59e0b",
          borderColor: "#f59e0b",
          pointRadius: 4.5,
          pointHoverRadius: 7
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            labels: { color: "#94a3b8", font: { family: "Inter", size: 12 } }
          },
          tooltip: {
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            titleColor: "#f8fafc",
            bodyColor: "#f59e0b",
            borderColor: "rgba(255, 255, 255, 0.1)",
            borderWidth: 1,
            padding: 10,
            callbacks: {
              label: (ctx) => {
                const pt = ctx.raw;
                return [
                  ` Date: ${pt.date || "N/A"}`,
                  ` X (${spec.x}): ${Number(pt.x).toLocaleString("en-IN")}`,
                  ` Y (${spec.y}): ${Number(pt.y).toLocaleString("en-IN")}`
                ];
              }
            }
          }
        },
        scales: {
          x: {
            title: {
              display: true,
              text: spec.x_label || spec.x,
              color: "#94a3b8",
              font: { family: "Inter", size: 12 }
            },
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            ticks: { color: "#94a3b8", font: { family: "Inter", size: 11 } }
          },
          y: {
            title: {
              display: true,
              text: spec.y_label || spec.y,
              color: "#94a3b8",
              font: { family: "Inter", size: 12 }
            },
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            ticks: { color: "#94a3b8", font: { family: "Inter", size: 11 } }
          }
        }
      }
    });
  }

  _renderPie(ctx, spec) {
    const labels = (spec.data || []).map(d => d.category || Object.values(d)[0]);
    const values = (spec.data || []).map(d => d.value !== undefined ? d.value : Object.values(d)[1]);

    const palette = [
      "#10b981", "#3b82f6", "#f59e0b", "#ec4899", 
      "#8b5cf6", "#06b6d4", "#14b8a6", "#f97316"
    ];

    return new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: palette.slice(0, labels.length),
          borderColor: "#0f1520",
          borderWidth: 2,
          hoverOffset: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "right",
            labels: { color: "#94a3b8", font: { family: "Inter", size: 12 }, padding: 14 }
          },
          tooltip: {
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            padding: 10,
            callbacks: {
              label: (ctx) => ` ${ctx.label}: ${Number(ctx.raw).toLocaleString("en-IN")} qtl`
            }
          }
        }
      }
    });
  }

  _renderTable(container, spec) {
    const tableWrap = document.createElement("div");
    tableWrap.className = "table-container";
    
    const records = spec.data || [];
    if (!records.length) return null;

    const cols = spec.columns || Object.keys(records[0]);

    let thHtml = cols.map(c => `<th>${c.replace(/_/g, ' ')}</th>`).join("");
    let tbHtml = records.slice(0, 15).map(r => {
      return `<tr>${cols.map(c => `<td>${r[c] !== undefined && r[c] !== null ? r[c] : '-'}</td>`).join("")}</tr>`;
    }).join("");

    tableWrap.innerHTML = `
      <table class="data-table">
        <thead><tr>${thHtml}</tr></thead>
        <tbody>${tbHtml}</tbody>
      </table>
    `;
    container.appendChild(tableWrap);
    return null;
  }
}

window.ChartRenderer = new ChartRenderer();
