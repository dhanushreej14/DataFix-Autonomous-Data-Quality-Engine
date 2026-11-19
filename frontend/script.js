/**
 * DataFix – Autonomous Data Quality & Repair Engine
 * SaaS Dashboard, Ingestion & Diagnostic Analysis Controller
 */

document.addEventListener("DOMContentLoaded", () => {
  console.log("[DataFix] Autonomous Engine initialized.");

  // Initialize UI controls, Views, and Handlers
  setupMobileSidebar();
  setupNavigation();
  initQualityTrendChart();
  initErrorDistributionChart();
  setupDashboardInteractions();
  setupDatasetUpload();
  setupDataAnalysis();
  setupAdvancedDataRepair();
  setupReportsPage();
  setupSettingsTab();
});

/**
 * Mobile Sidebar Drawer Handling
 */
function setupMobileSidebar() {
  const sidebar = document.getElementById("sidebar");
  const menuToggleBtn = document.getElementById("menuToggleBtn");
  const mobileCloseBtn = document.getElementById("mobileCloseBtn");
  const sidebarOverlay = document.getElementById("sidebarOverlay");

  const openSidebar = () => {
    sidebar.classList.add("open");
    sidebarOverlay.classList.add("active");
    document.body.style.overflow = "hidden";
  };

  const closeSidebar = () => {
    sidebar.classList.remove("open");
    sidebarOverlay.classList.remove("active");
    document.body.style.overflow = "";
  };

  if (menuToggleBtn) menuToggleBtn.addEventListener("click", openSidebar);
  if (mobileCloseBtn) mobileCloseBtn.addEventListener("click", closeSidebar);
  if (sidebarOverlay) sidebarOverlay.addEventListener("click", closeSidebar);
}

/**
 * Global Tab Navigation & View Switcher
 * Makes ALL 6 navigation links fully functional without unnecessary reloads
 */
let analysisChartsInitialized = false;
let reportsChartsInitialized = false;

function setupNavigation() {
  const navLinks = document.querySelectorAll(".nav-link");
  const crumbCurrent = document.querySelector(".crumb-current");
  const tabViews = document.querySelectorAll(".tab-view");
  const brandLogoLink = document.getElementById("brandLogoLink");
  const crumbRoot = document.getElementById("crumbRoot");
  const viewAllActivityBtn = document.getElementById("viewAllActivityBtn");

  const TAB_LABELS = {
    dashboard: "Dashboard",
    upload: "Upload Dataset",
    analysis: "Data Analysis",
    repair: "Data Repair",
    reports: "Reports",
    settings: "Settings"
  };

  const viewMap = {
    dashboard: document.getElementById("view-dashboard"),
    upload: document.getElementById("view-upload"),
    analysis: document.getElementById("view-analysis"),
    repair: document.getElementById("view-repair"),
    reports: document.getElementById("view-reports"),
    settings: document.getElementById("view-settings")
  };

  const switchView = (tabKey, updateHash = true) => {
    const key = (tabKey || "dashboard").toLowerCase().replace("#", "").trim();
    const validKey = viewMap[key] ? key : "dashboard";
    const tabLabel = TAB_LABELS[validKey] || "Dashboard";

    // 1. Hide all view panes and show target view
    tabViews.forEach((view) => {
      view.classList.add("hidden");
      view.classList.remove("active");
    });

    const targetView = viewMap[validKey];
    if (targetView) {
      targetView.classList.remove("hidden");
      targetView.classList.add("active");
    }

    // 2. Highlight currently selected sidebar menu item
    navLinks.forEach((item) => {
      if (item.getAttribute("data-tab") === validKey) {
        item.classList.add("active");
        item.setAttribute("aria-current", "page");
      } else {
        item.classList.remove("active");
        item.removeAttribute("aria-current");
      }
    });

    // 3. Update topbar breadcrumb
    if (crumbCurrent) {
      crumbCurrent.textContent = tabLabel;
    }

    // 4. Update URL hash without reloading page
    if (updateHash) {
      if (history.pushState) {
        history.pushState(null, "", `#${validKey}`);
      } else {
        window.location.hash = validKey;
      }
    }

    // 5. Trigger charts layout adjustments / initialization
    if (validKey === "dashboard" && qualityChartInstance) {
      setTimeout(() => qualityChartInstance.resize(), 100);
    } else if (validKey === "analysis") {
      if (!analysisChartsInitialized) {
        initDataAnalysisCharts();
        analysisChartsInitialized = true;
      } else {
        setTimeout(() => {
          if (window.analysisCategoryChartInstance) window.analysisCategoryChartInstance.resize();
          if (window.analysisColumnChartInstance) window.analysisColumnChartInstance.resize();
        }, 100);
      }
    } else if (validKey === "reports") {
      if (!reportsChartsInitialized) {
        initQualityComparisonChart();
        reportsChartsInitialized = true;
      } else {
        setTimeout(() => {
          if (window.qualityComparisonChartInstance) window.qualityComparisonChartInstance.resize();
        }, 100);
      }
    }

    // 6. Smooth scroll to top of workspace
    window.scrollTo({ top: 0, behavior: "smooth" });

    // 7. Close mobile drawer if active
    const sidebar = document.getElementById("sidebar");
    const sidebarOverlay = document.getElementById("sidebarOverlay");
    if (sidebar && sidebar.classList.contains("open")) {
      sidebar.classList.remove("open");
      if (sidebarOverlay) sidebarOverlay.classList.remove("active");
      document.body.style.overflow = "";
    }
  };

  // Attach click listeners to sidebar navigation items
  navLinks.forEach((link) => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const tabKey = link.getAttribute("data-tab");
      switchView(tabKey, true);
    });
  });

  // Brand Logo and Breadcrumb Root navigate to Dashboard
  if (brandLogoLink) {
    brandLogoLink.addEventListener("click", (e) => {
      e.preventDefault();
      switchView("dashboard", true);
    });
  }

  if (crumbRoot) {
    crumbRoot.addEventListener("click", (e) => {
      e.preventDefault();
      switchView("dashboard", true);
    });
  }

  // Dashboard "View Full Audit Log" button navigates to Data Analysis
  if (viewAllActivityBtn) {
    viewAllActivityBtn.addEventListener("click", () => {
      switchView("analysis", true);
    });
  }

  // Recent Activity Table rows click navigates to Data Analysis
  const activityRows = document.querySelectorAll("#activityTableBody tr");
  activityRows.forEach((row) => {
    row.style.cursor = "pointer";
    row.title = "Click to inspect dataset in Data Analysis";
    row.addEventListener("click", () => {
      switchView("analysis", true);
    });
  });

  // Browser Back / Forward History Navigation Listener
  window.addEventListener("popstate", () => {
    const hash = window.location.hash.replace("#", "").trim();
    switchView(hash || "dashboard", false);
  });

  window.addEventListener("hashchange", () => {
    const hash = window.location.hash.replace("#", "").trim();
    switchView(hash || "dashboard", false);
  });

  // Global helper for cross-component routing
  window.navigateToTab = (tabKey) => switchView(tabKey, true);

  // Initialize view from URL hash if present, otherwise default to dashboard
  const initialHash = window.location.hash.replace("#", "").trim();
  switchView(initialHash || "dashboard", false);
}

/**
 * Main Quality & Autonomous Repair Trend Chart (Chart.js)
 */
let qualityChartInstance = null;

function initQualityTrendChart() {
  const ctx = document.getElementById("qualityChart");
  if (!ctx || typeof Chart === "undefined") return;

  const chartContext = ctx.getContext("2d");

  const purpleGradient = chartContext.createLinearGradient(0, 0, 0, 260);
  purpleGradient.addColorStop(0, "rgba(139, 92, 246, 0.35)");
  purpleGradient.addColorStop(1, "rgba(139, 92, 246, 0.0)");

  const greenGradient = chartContext.createLinearGradient(0, 0, 0, 260);
  greenGradient.addColorStop(0, "rgba(16, 185, 129, 0.35)");
  greenGradient.addColorStop(1, "rgba(16, 185, 129, 0.0)");

  const dataSetsByPeriod = {
    "7d": {
      labels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
      scores: [94.2, 95.8, 96.1, 95.5, 97.4, 98.1, 98.4],
      repaired: [420, 680, 590, 810, 940, 620, 1132]
    },
    "30d": {
      labels: ["Week 1", "Week 2", "Week 3", "Week 4"],
      scores: [92.0, 94.6, 96.8, 98.4],
      repaired: [2400, 3100, 3900, 5192]
    },
    "90d": {
      labels: ["Month 1", "Month 2", "Month 3"],
      scores: [88.5, 93.2, 98.4],
      repaired: [8200, 12400, 17800]
    }
  };

  qualityChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: dataSetsByPeriod["7d"].labels,
      datasets: [
        {
          label: "Data Quality Score (%)",
          data: dataSetsByPeriod["7d"].scores,
          borderColor: "#10b981",
          backgroundColor: greenGradient,
          fill: true,
          tension: 0.4,
          pointBackgroundColor: "#10b981",
          pointBorderColor: "#0f121a",
          pointBorderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 6,
          yAxisID: "y"
        },
        {
          label: "Repaired Records",
          data: dataSetsByPeriod["7d"].repaired,
          borderColor: "#8b5cf6",
          backgroundColor: purpleGradient,
          fill: true,
          tension: 0.4,
          pointBackgroundColor: "#8b5cf6",
          pointBorderColor: "#0f121a",
          pointBorderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 6,
          yAxisID: "y1"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          display: true,
          position: "top",
          align: "end",
          labels: {
            color: "#94a3b8",
            usePointStyle: true,
            boxWidth: 8,
            font: { family: "'Plus Jakarta Sans', sans-serif", size: 12 }
          }
        },
        tooltip: {
          backgroundColor: "#191e2e",
          titleColor: "#f8fafc",
          bodyColor: "#94a3b8",
          borderColor: "#232a3e",
          borderWidth: 1,
          padding: 10,
          boxPadding: 4,
          usePointStyle: true
        }
      },
      scales: {
        x: {
          grid: { color: "rgba(255, 255, 255, 0.04)" },
          ticks: { color: "#64748b", font: { family: "'Plus Jakarta Sans', sans-serif" } }
        },
        y: {
          type: "linear",
          display: true,
          position: "left",
          min: 80,
          max: 100,
          grid: { color: "rgba(255, 255, 255, 0.04)" },
          ticks: {
            color: "#64748b",
            font: { family: "'Plus Jakarta Sans', sans-serif" },
            callback: (val) => `${val}%`
          }
        },
        y1: {
          type: "linear",
          display: true,
          position: "right",
          grid: { drawOnChartArea: false },
          ticks: { color: "#64748b", font: { family: "'Plus Jakarta Sans', sans-serif" } }
        }
      }
    }
  });

  const periodButtons = document.querySelectorAll(".pill-btn[data-period]");
  periodButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      periodButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      const period = btn.getAttribute("data-period");
      const config = dataSetsByPeriod[period];
      if (config && qualityChartInstance) {
        qualityChartInstance.data.labels = config.labels;
        qualityChartInstance.data.datasets[0].data = config.scores;
        qualityChartInstance.data.datasets[1].data = config.repaired;
        qualityChartInstance.update();
      }
    });
  });
}

/**
 * Doughnut Chart: Error Classifications (Dashboard)
 */
function initErrorDistributionChart() {
  const ctx = document.getElementById("errorDistributionChart");
  if (!ctx || typeof Chart === "undefined") return;

  new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Missing Values", "Type Mismatches", "Outliers / Invalid", "Duplicate Rows"],
      datasets: [
        {
          data: [42, 28, 19, 11],
          backgroundColor: ["#8b5cf6", "#10b981", "#f59e0b", "#ec4899"],
          borderWidth: 3,
          borderColor: "#191e2e",
          hoverOffset: 4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "75%",
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#191e2e",
          titleColor: "#f8fafc",
          bodyColor: "#94a3b8",
          borderColor: "#232a3e",
          borderWidth: 1,
          padding: 8,
          callbacks: {
            label: (item) => ` ${item.label}: ${item.raw}%`
          }
        }
      }
    }
  });
}

/**
 * Quick Actions on Dashboard
 */
function setupDashboardInteractions() {
  const triggerScanBtn = document.getElementById("triggerScanBtn");
  const newDatasetBtn = document.getElementById("newDatasetBtn");

  if (triggerScanBtn) {
    triggerScanBtn.addEventListener("click", () => {
      const originalText = triggerScanBtn.innerHTML;
      triggerScanBtn.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
          <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
          <path d="M12 2a10 10 0 0 1 10 10"></path>
        </svg> Scanning Streams...
      `;
      triggerScanBtn.style.pointerEvents = "none";

      setTimeout(() => {
        triggerScanBtn.innerHTML = `✓ Scan Complete`;
        triggerScanBtn.style.color = "#34d399";
        triggerScanBtn.style.borderColor = "rgba(16, 185, 129, 0.4)";

        setTimeout(() => {
          triggerScanBtn.innerHTML = originalText;
          triggerScanBtn.style.pointerEvents = "";
          triggerScanBtn.style.color = "";
          triggerScanBtn.style.borderColor = "";
        }, 2200);
      }, 1500);
    });
  }

  if (newDatasetBtn) {
    newDatasetBtn.addEventListener("click", () => {
      if (window.navigateToTab) window.navigateToTab("upload", "Upload Dataset");
    });
  }
}

/**
 * ==========================================================================
 * Dataset Upload & File Validation Logic
 * ==========================================================================
 */
function setupDatasetUpload() {
  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("datasetFileInput");
  const browseFilesBtn = document.getElementById("browseFilesBtn");
  const uploadAlert = document.getElementById("uploadAlert");
  const alertTitle = document.getElementById("alertTitle");
  const alertMessage = document.getElementById("alertMessage");
  const closeAlertBtn = document.getElementById("closeAlertBtn");

  const filePreviewCard = document.getElementById("filePreviewCard");
  const previewFileName = document.getElementById("previewFileName");
  const previewFileSize = document.getElementById("previewFileSize");
  const previewFileType = document.getElementById("previewFileType");
  const previewFileIcon = document.getElementById("previewFileIcon");
  const previewExtBadge = document.getElementById("previewExtBadge");
  const previewStatus = document.getElementById("previewStatus");
  const removeFileBtn = document.getElementById("removeFileBtn");
  const replaceFileBtn = document.getElementById("replaceFileBtn");

  const scanDatasetBtn = document.getElementById("scanDatasetBtn");
  const scanBtnText = document.getElementById("scanBtnText");
  const scanProgressBarWrapper = document.getElementById("scanProgressBarWrapper");
  const scanStatusText = document.getElementById("scanStatusText");
  const scanPercentText = document.getElementById("scanPercentText");
  const scanProgressFill = document.getElementById("scanProgressFill");
  const scanResultsCard = document.getElementById("scanResultsCard");
  const proceedRepairBtn = document.getElementById("proceedRepairBtn");

  const ALLOWED_EXTENSIONS = [".csv", ".xls", ".xlsx"];
  const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100 MB

  let currentFile = null;
  let isScanning = false;

  const formatFileSize = (bytes) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const showAlert = (title, message, isWarning = false) => {
    if (!uploadAlert) return;
    if (alertTitle) alertTitle.textContent = title;
    if (alertMessage) alertMessage.textContent = message;

    if (isWarning) {
      uploadAlert.classList.add("warning");
    } else {
      uploadAlert.classList.remove("warning");
    }
    uploadAlert.classList.remove("hidden");
  };

  const hideAlert = () => {
    if (uploadAlert) uploadAlert.classList.add("hidden");
  };

  const resetUploadState = () => {
    currentFile = null;
    isScanning = false;
    if (fileInput) fileInput.value = "";
    if (filePreviewCard) filePreviewCard.classList.add("hidden");
    if (scanProgressBarWrapper) scanProgressBarWrapper.classList.add("hidden");
    if (scanResultsCard) scanResultsCard.classList.add("hidden");
    if (dropZone) dropZone.classList.remove("hidden");
    if (scanDatasetBtn) {
      scanDatasetBtn.disabled = false;
      if (scanBtnText) scanBtnText.textContent = "Scan Dataset";
    }
    hideAlert();
  };

  const processSelectedFile = (file) => {
    if (!file) return;
    hideAlert();

    const fileName = file.name.trim();
    const lastDotIndex = fileName.lastIndexOf(".");
    const ext = lastDotIndex !== -1 ? fileName.substring(lastDotIndex).toLowerCase() : "";

    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      showAlert(
        "Invalid File Type",
        `"${fileName}" is not supported. Please upload a valid CSV, XLS, or XLSX file.`
      );
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      showAlert(
        "File Too Large",
        `"${fileName}" exceeds the 100 MB limit. Please select a smaller dataset.`,
        true
      );
      return;
    }

    currentFile = file;
    const isExcel = ext === ".xls" || ext === ".xlsx";
    const badgeText = ext.replace(".", "").toUpperCase();

    if (previewExtBadge) previewExtBadge.textContent = badgeText;
    if (previewFileIcon) {
      if (isExcel) {
        previewFileIcon.classList.add("excel");
      } else {
        previewFileIcon.classList.remove("excel");
      }
    }

    if (previewFileName) previewFileName.textContent = fileName;
    if (previewFileSize) previewFileSize.textContent = formatFileSize(file.size);
    if (previewFileType) {
      previewFileType.textContent = isExcel ? `Excel Spreadsheet (${badgeText})` : "CSV Dataset";
    }
    if (previewStatus) {
      previewStatus.className = "status-pill status-success";
      previewStatus.textContent = "Ready for Scan";
    }

    if (scanProgressBarWrapper) scanProgressBarWrapper.classList.add("hidden");
    if (scanProgressFill) scanProgressFill.style.width = "0%";
    if (scanResultsCard) scanResultsCard.classList.add("hidden");

    if (scanDatasetBtn) {
      scanDatasetBtn.disabled = false;
      if (scanBtnText) scanBtnText.textContent = "Scan Dataset";
    }

    if (filePreviewCard) filePreviewCard.classList.remove("hidden");
    console.log(`[DataFix] Valid file loaded: ${fileName}`);
  };

  if (browseFilesBtn && fileInput) {
    browseFilesBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      fileInput.click();
    });
  }

  if (dropZone && fileInput) {
    dropZone.addEventListener("click", () => fileInput.click());
  }

  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        processSelectedFile(e.target.files[0]);
      }
    });
  }

  if (dropZone) {
    const highlightDrag = (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add("dragover");
    };

    const unhighlightDrag = (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove("dragover");
    };

    dropZone.addEventListener("dragenter", highlightDrag);
    dropZone.addEventListener("dragover", highlightDrag);
    dropZone.addEventListener("dragleave", unhighlightDrag);
    dropZone.addEventListener("drop", (e) => {
      unhighlightDrag(e);
      const dt = e.dataTransfer;
      if (dt.files && dt.files.length > 0) {
        processSelectedFile(dt.files[0]);
      }
    });
  }

  if (closeAlertBtn) closeAlertBtn.addEventListener("click", hideAlert);
  if (removeFileBtn) removeFileBtn.addEventListener("click", resetUploadState);
  if (replaceFileBtn && fileInput) replaceFileBtn.addEventListener("click", () => fileInput.click());

  if (scanDatasetBtn) {
    scanDatasetBtn.addEventListener("click", () => {
      if (!currentFile || isScanning) return;

      isScanning = true;
      scanDatasetBtn.disabled = true;
      if (scanResultsCard) scanResultsCard.classList.add("hidden");
      if (scanProgressBarWrapper) scanProgressBarWrapper.classList.remove("hidden");

      if (previewStatus) {
        previewStatus.className = "status-pill status-processing";
        previewStatus.textContent = "Scanning Anomalies...";
      }

      if (scanBtnText) {
        scanBtnText.innerHTML = `
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
            <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
            <path d="M12 2a10 10 0 0 1 10 10"></path>
          </svg> Analyzing Schema...
        `;
      }

      const stages = [
        { progress: 20, text: "Reading file headers & schema..." },
        { progress: 48, text: "Profiling columns for type mismatches..." },
        { progress: 75, text: "Detecting missing values & distribution outliers..." },
        { progress: 95, text: "Generating autonomous repair recipe..." },
        { progress: 100, text: "Audit complete." }
      ];

      let stageIdx = 0;
      const interval = setInterval(() => {
        if (stageIdx < stages.length) {
          const currentStage = stages[stageIdx];
          if (scanProgressFill) scanProgressFill.style.width = `${currentStage.progress}%`;
          if (scanPercentText) scanPercentText.textContent = `${currentStage.progress}%`;
          if (scanStatusText) scanStatusText.textContent = currentStage.text;
          stageIdx++;
        } else {
          clearInterval(interval);
          isScanning = false;

          if (previewStatus) {
            previewStatus.className = "status-pill status-success";
            previewStatus.textContent = "Scan Complete • 92.6% Health";
          }

          if (scanBtnText) scanBtnText.textContent = "Re-Scan Dataset";
          scanDatasetBtn.disabled = false;

          const estimatedRows = Math.max(120, Math.floor(currentFile.size / 75));
          const resRowCount = document.getElementById("resRowCount");
          if (resRowCount) resRowCount.textContent = estimatedRows.toLocaleString();

          if (scanResultsCard) scanResultsCard.classList.remove("hidden");
        }
      }, 300);
    });
  }

  if (proceedRepairBtn) {
    proceedRepairBtn.addEventListener("click", () => {
      if (window.navigateToTab) window.navigateToTab("repair", "Data Repair");
    });
  }
}

/**
 * ==========================================================================
 * Data Analysis Page Controller & Interactive Diagnostics
 * ==========================================================================
 */
function setupDataAnalysis() {
  const analysisScanBtn = document.getElementById("analysisScanBtn");
  const analysisScanBtnText = document.getElementById("analysisScanBtnText");
  const errorSearchInput = document.getElementById("errorSearchInput");
  const categoryFilterSelect = document.getElementById("categoryFilterSelect");
  const severityFilterSelect = document.getElementById("severityFilterSelect");
  const clearFiltersBtn = document.getElementById("clearFiltersBtn");
  const resetCategoryFilterBtn = document.getElementById("resetCategoryFilterBtn");
  const categoryCards = document.querySelectorAll(".category-card");
  const tableRows = document.querySelectorAll("#errorTableBody tr");
  const tableRecordCount = document.getElementById("tableRecordCount");
  const goToRepairBtn = document.getElementById("goToRepairBtn");
  const exportAuditBtn = document.getElementById("exportAuditBtn");

  // Filtering Logic
  const applyTableFilters = () => {
    const searchTerm = errorSearchInput ? errorSearchInput.value.toLowerCase().trim() : "";
    const selectedCategory = categoryFilterSelect ? categoryFilterSelect.value : "all";
    const selectedSeverity = severityFilterSelect ? severityFilterSelect.value : "all";

    let visibleCount = 0;

    tableRows.forEach((row) => {
      const rowCat = row.getAttribute("data-cat");
      const rowSev = row.getAttribute("data-sev");
      const rowText = row.textContent.toLowerCase();

      const matchesSearch = !searchTerm || rowText.includes(searchTerm);
      const matchesCategory = selectedCategory === "all" || rowCat === selectedCategory;
      const matchesSeverity = selectedSeverity === "all" || rowSev === selectedSeverity;

      if (matchesSearch && matchesCategory && matchesSeverity) {
        row.style.display = "";
        visibleCount++;
      } else {
        row.style.display = "none";
      }
    });

    if (tableRecordCount) {
      tableRecordCount.textContent = `Showing ${visibleCount} of ${tableRows.length} diagnostic samples (Total dataset errors: 1,824)`;
    }
  };

  // Attach search and select listeners
  if (errorSearchInput) errorSearchInput.addEventListener("input", applyTableFilters);
  if (categoryFilterSelect) categoryFilterSelect.addEventListener("change", applyTableFilters);
  if (severityFilterSelect) severityFilterSelect.addEventListener("change", applyTableFilters);

  // Reset Filters
  const resetAllFilters = () => {
    if (errorSearchInput) errorSearchInput.value = "";
    if (categoryFilterSelect) categoryFilterSelect.value = "all";
    if (severityFilterSelect) severityFilterSelect.value = "all";
    categoryCards.forEach((c) => c.classList.remove("active-filter"));
    applyTableFilters();
  };

  if (clearFiltersBtn) clearFiltersBtn.addEventListener("click", resetAllFilters);
  if (resetCategoryFilterBtn) resetCategoryFilterBtn.addEventListener("click", resetAllFilters);

  // Category Cards Interactive Filter Click
  categoryCards.forEach((card) => {
    card.addEventListener("click", () => {
      const category = card.getAttribute("data-cat-filter");
      const isAlreadyActive = card.classList.contains("active-filter");

      categoryCards.forEach((c) => c.classList.remove("active-filter"));

      if (!isAlreadyActive && category) {
        card.classList.add("active-filter");
        if (categoryFilterSelect) categoryFilterSelect.value = category;
      } else {
        if (categoryFilterSelect) categoryFilterSelect.value = "all";
      }

      applyTableFilters();
    });
  });

  // Scan Dataset Button on Analysis Page (Simulated Re-audit)
  if (analysisScanBtn) {
    analysisScanBtn.addEventListener("click", () => {
      const originalText = analysisScanBtnText ? analysisScanBtnText.textContent : "Scan Dataset";
      if (analysisScanBtnText) {
        analysisScanBtnText.innerHTML = `
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
            <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
            <path d="M12 2a10 10 0 0 1 10 10"></path>
          </svg> Auditing 642.8K Records...
        `;
      }
      analysisScanBtn.disabled = true;

      setTimeout(() => {
        if (analysisScanBtnText) analysisScanBtnText.textContent = "✓ Scan Complete";
        analysisScanBtn.style.color = "#34d399";

        // Refresh score bar with subtle bounce
        const scoreBar = document.getElementById("analysisScoreBar");
        if (scoreBar) {
          scoreBar.style.width = "94.2%";
          const scoreVal = document.getElementById("analysisQualityScore");
          if (scoreVal) scoreVal.textContent = "94.2%";
        }

        setTimeout(() => {
          if (analysisScanBtnText) analysisScanBtnText.textContent = originalText;
          analysisScanBtn.disabled = false;
          analysisScanBtn.style.color = "";
        }, 2000);
      }, 1400);
    });
  }

  // Cross-Navigation & Quick Actions
  if (goToRepairBtn) {
    goToRepairBtn.addEventListener("click", () => {
      if (window.navigateToTab) window.navigateToTab("repair", "Data Repair");
    });
  }

  if (exportAuditBtn) {
    exportAuditBtn.addEventListener("click", () => {
      const original = exportAuditBtn.innerHTML;
      exportAuditBtn.innerHTML = "Exporting CSV...";
      setTimeout(() => {
        exportAuditBtn.innerHTML = "✓ Audit Exported";
        setTimeout(() => {
          exportAuditBtn.innerHTML = original;
        }, 1800);
      }, 800);
    });
  }

  // Row "Inspect" buttons navigate directly to Data Repair studio
  const inspectBtns = document.querySelectorAll(".action-table-btn");
  inspectBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (window.navigateToTab) window.navigateToTab("repair");
    });
  });
}

/**
 * Initialize Interactive Charts for Data Analysis
 */
function initDataAnalysisCharts() {
  if (typeof Chart === "undefined") return;

  // Chart 1: Error Distribution across the 5 Problem Types
  const ctxCategory = document.getElementById("analysisCategoryChart");
  if (ctxCategory) {
    window.analysisCategoryChartInstance = new Chart(ctxCategory, {
      type: "bar",
      data: {
        labels: [
          "1. Missing Values",
          "2. Duplicate Records",
          "3. Invalid Formats",
          "4. Inconsistent Values",
          "5. Outliers"
        ],
        datasets: [
          {
            label: "Detected Errors",
            data: [684, 210, 412, 328, 190],
            backgroundColor: [
              "rgba(139, 92, 246, 0.85)", // Purple
              "rgba(236, 72, 153, 0.85)", // Pink
              "rgba(239, 68, 68, 0.85)",  // Red
              "rgba(245, 158, 11, 0.85)", // Amber
              "rgba(16, 185, 129, 0.85)"  // Green
            ],
            borderRadius: 6,
            borderSkipped: false
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#191e2e",
            titleColor: "#f8fafc",
            bodyColor: "#94a3b8",
            borderColor: "#232a3e",
            borderWidth: 1,
            padding: 10,
            callbacks: {
              label: (item) => ` ${item.raw.toLocaleString()} errors (${((item.raw / 1824) * 100).toFixed(1)}%)`
            }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: "#94a3b8",
              font: { family: "'Plus Jakarta Sans', sans-serif", size: 11 }
            }
          },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.04)" },
            ticks: {
              color: "#64748b",
              font: { family: "'Plus Jakarta Sans', sans-serif" }
            }
          }
        }
      }
    });
  }

  // Chart 2: Column Integrity & Health Rate
  const ctxColumn = document.getElementById("analysisColumnChart");
  if (ctxColumn) {
    const colCtx = ctxColumn.getContext("2d");
    const barGradient = colCtx.createLinearGradient(0, 0, 0, 260);
    barGradient.addColorStop(0, "rgba(16, 185, 129, 0.8)");
    barGradient.addColorStop(1, "rgba(139, 92, 246, 0.8)");

    window.analysisColumnChartInstance = new Chart(ctxColumn, {
      type: "bar",
      data: {
        labels: ["user_id", "email", "tax_id", "postal_code", "state_code", "amount_usd", "currency"],
        datasets: [
          {
            label: "Field Health (%)",
            data: [99.9, 88.2, 76.5, 82.4, 91.0, 94.6, 95.8],
            backgroundColor: barGradient,
            borderRadius: 6
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#191e2e",
            titleColor: "#f8fafc",
            bodyColor: "#94a3b8",
            borderColor: "#232a3e",
            borderWidth: 1,
            padding: 10,
            callbacks: {
              label: (item) => ` Health Score: ${item.raw}% valid`
            }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: "#94a3b8",
              font: { family: "'Plus Jakarta Sans', sans-serif", size: 11 }
            }
          },
          y: {
            min: 60,
            max: 100,
            grid: { color: "rgba(255, 255, 255, 0.04)" },
            ticks: {
              color: "#64748b",
              callback: (val) => `${val}%`
            }
          }
        }
      }
    });
  }
}

/**
 * ==========================================================================
 * Advanced Data Repair Studio Controller
 * Human-in-the-loop review, approve, reject, bulk actions & commit
 * ==========================================================================
 */
function setupAdvancedDataRepair() {
  const repairTable = document.getElementById("repairTable");
  const selectAllCheckbox = document.getElementById("selectAllCheckbox");
  const rowCheckboxes = document.querySelectorAll(".row-checkbox");
  const repairRows = document.querySelectorAll("#repairTableBody tr");

  const bulkApproveBtn = document.getElementById("bulkApproveBtn");
  const bulkRejectBtn = document.getElementById("bulkRejectBtn");
  const resetRepairsBtn = document.getElementById("resetRepairsBtn");
  const applyRepairsBtn = document.getElementById("applyRepairsBtn");
  const applyRepairsBtnText = document.getElementById("applyRepairsBtnText");
  const bottomApplyBtn = document.getElementById("bottomApplyBtn");

  const approvedCountEl = document.getElementById("approvedCount");
  const rejectedCountEl = document.getElementById("rejectedCount");
  const pendingCountEl = document.getElementById("pendingCount");
  const totalProposalsCountEl = document.getElementById("totalProposalsCount");

  const repairToast = document.getElementById("repairToast");
  const toastTitle = document.getElementById("toastTitle");
  const toastMessage = document.getElementById("toastMessage");
  const closeToastBtn = document.getElementById("closeToastBtn");

  let toastTimeout = null;

  // Show Toast Notification
  const showToast = (title, message, isError = false) => {
    if (!repairToast) return;
    if (toastTitle) toastTitle.textContent = title;
    if (toastMessage) toastMessage.textContent = message;

    if (isError) {
      repairToast.classList.add("error-toast");
    } else {
      repairToast.classList.remove("error-toast");
    }

    repairToast.classList.remove("hidden");

    if (toastTimeout) clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => {
      repairToast.classList.add("hidden");
    }, 5500);
  };

  if (closeToastBtn) {
    closeToastBtn.addEventListener("click", () => {
      if (repairToast) repairToast.classList.add("hidden");
      if (toastTimeout) clearTimeout(toastTimeout);
    });
  }

  // Recalculate and update summary counters
  const updateCounters = () => {
    let approved = 0;
    let rejected = 0;
    let committed = 0;
    let total = repairRows.length;

    repairRows.forEach((row) => {
      if (row.classList.contains("row-approved")) approved++;
      else if (row.classList.contains("row-rejected")) rejected++;
      else if (row.classList.contains("row-committed")) committed++;
    });

    const pending = total - (approved + rejected + committed);

    if (approvedCountEl) approvedCountEl.textContent = approved;
    if (rejectedCountEl) rejectedCountEl.textContent = rejected;
    if (pendingCountEl) pendingCountEl.textContent = Math.max(0, pending);
    if (totalProposalsCountEl) totalProposalsCountEl.textContent = total;

    // Toggle Apply Buttons
    const hasApproved = approved > 0;
    if (applyRepairsBtn) {
      applyRepairsBtn.disabled = !hasApproved;
      if (applyRepairsBtnText) {
        applyRepairsBtnText.textContent = hasApproved
          ? `Apply Approved Repairs (${approved})`
          : "Apply Approved Repairs (0)";
      }
    }
    if (bottomApplyBtn) {
      bottomApplyBtn.disabled = !hasApproved;
      bottomApplyBtn.textContent = hasApproved
        ? `Apply Approved Repairs (${approved})`
        : "Apply Approved Repairs";
    }
  };

  // Approve a single row
  const approveRow = (row) => {
    if (row.classList.contains("row-committed")) return;

    row.classList.remove("row-rejected");
    row.classList.add("row-approved");

    const cb = row.querySelector(".row-checkbox");
    if (cb) cb.checked = true;

    const actionBtns = row.querySelector(".row-action-btns");
    const statusBadge = row.querySelector(".row-status-badge");

    if (actionBtns) actionBtns.classList.add("hidden");
    if (statusBadge) {
      statusBadge.className = "row-status-badge badge-approved";
      statusBadge.innerHTML = `✓ Approved <button type="button" class="undo-btn">Undo</button>`;
      statusBadge.classList.remove("hidden");

      const undoBtn = statusBadge.querySelector(".undo-btn");
      if (undoBtn) undoBtn.addEventListener("click", () => resetRow(row));
    }

    updateCounters();
  };

  // Reject a single row
  const rejectRow = (row) => {
    if (row.classList.contains("row-committed")) return;

    row.classList.remove("row-approved");
    row.classList.add("row-rejected");

    const cb = row.querySelector(".row-checkbox");
    if (cb) cb.checked = false;

    const actionBtns = row.querySelector(".row-action-btns");
    const statusBadge = row.querySelector(".row-status-badge");

    if (actionBtns) actionBtns.classList.add("hidden");
    if (statusBadge) {
      statusBadge.className = "row-status-badge badge-rejected";
      statusBadge.innerHTML = `✕ Rejected <button type="button" class="undo-btn">Undo</button>`;
      statusBadge.classList.remove("hidden");

      const undoBtn = statusBadge.querySelector(".undo-btn");
      if (undoBtn) undoBtn.addEventListener("click", () => resetRow(row));
    }

    updateCounters();
  };

  // Reset a single row to pending review
  const resetRow = (row) => {
    row.classList.remove("row-approved", "row-rejected", "row-committed");

    const cb = row.querySelector(".row-checkbox");
    if (cb) {
      cb.checked = false;
      cb.disabled = false;
    }

    const actionBtns = row.querySelector(".row-action-btns");
    const statusBadge = row.querySelector(".row-status-badge");

    if (actionBtns) actionBtns.classList.remove("hidden");
    if (statusBadge) {
      statusBadge.classList.add("hidden");
      statusBadge.innerHTML = "";
    }

    updateCounters();
  };

  // Attach individual approve & reject click listeners
  repairRows.forEach((row) => {
    const approveBtn = row.querySelector(".approve-btn");
    const rejectBtn = row.querySelector(".reject-btn");

    if (approveBtn) approveBtn.addEventListener("click", () => approveRow(row));
    if (rejectBtn) rejectBtn.addEventListener("click", () => rejectRow(row));
  });

  // Master Checkbox Select / Deselect All
  if (selectAllCheckbox) {
    selectAllCheckbox.addEventListener("change", (e) => {
      const isChecked = e.target.checked;
      rowCheckboxes.forEach((cb) => {
        if (!cb.disabled) cb.checked = isChecked;
      });
    });
  }

  // Row checkbox state update
  rowCheckboxes.forEach((cb) => {
    cb.addEventListener("change", () => {
      const allChecked = Array.from(rowCheckboxes).every((box) => box.checked);
      if (selectAllCheckbox) selectAllCheckbox.checked = allChecked;
    });
  });

  // Bulk Approve Selected Checkboxes
  if (bulkApproveBtn) {
    bulkApproveBtn.addEventListener("click", () => {
      let count = 0;
      repairRows.forEach((row) => {
        const cb = row.querySelector(".row-checkbox");
        if (cb && cb.checked && !row.classList.contains("row-committed")) {
          approveRow(row);
          count++;
        }
      });
      if (count > 0) {
        showToast("Proposals Approved", `${count} corrections marked as Approved for remediation.`);
      } else {
        showToast("No Rows Selected", "Please select one or more proposal checkboxes to bulk approve.", true);
      }
    });
  }

  // Bulk Reject Selected Checkboxes
  if (bulkRejectBtn) {
    bulkRejectBtn.addEventListener("click", () => {
      let count = 0;
      repairRows.forEach((row) => {
        const cb = row.querySelector(".row-checkbox");
        if (cb && cb.checked && !row.classList.contains("row-committed")) {
          rejectRow(row);
          count++;
        }
      });
      if (count > 0) {
        showToast("Proposals Rejected", `${count} corrections rejected and removed from staging.`);
      } else {
        showToast("No Rows Selected", "Please select one or more proposal checkboxes to bulk reject.", true);
      }
    });
  }

  // Reset All Button
  if (resetRepairsBtn) {
    resetRepairsBtn.addEventListener("click", () => {
      repairRows.forEach((row) => resetRow(row));
      if (selectAllCheckbox) selectAllCheckbox.checked = false;
      showToast("Reset Complete", "All proposed corrections restored to initial review state.");
    });
  }

  // Apply Approved Repairs Action Handler
  const executeApplyRepairs = () => {
    const approvedRows = Array.from(repairRows).filter((r) => r.classList.contains("row-approved"));
    const count = approvedRows.length;

    if (count === 0) {
      showToast("No Approved Repairs", "Please approve at least one correction proposal before applying.", true);
      return;
    }

    // Set buttons to loading spinner
    if (applyRepairsBtn) {
      applyRepairsBtn.disabled = true;
      if (applyRepairsBtnText) {
        applyRepairsBtnText.innerHTML = `
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
            <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
            <path d="M12 2a10 10 0 0 1 10 10"></path>
          </svg> Committing ${count} Repairs...
        `;
      }
    }
    if (bottomApplyBtn) bottomApplyBtn.disabled = true;

    setTimeout(() => {
      // Mark approved rows as committed
      approvedRows.forEach((row) => {
        row.classList.remove("row-approved");
        row.classList.add("row-committed");

        const cb = row.querySelector(".row-checkbox");
        if (cb) {
          cb.checked = false;
          cb.disabled = true;
        }

        const statusBadge = row.querySelector(".row-status-badge");
        if (statusBadge) {
          statusBadge.className = "row-status-badge badge-committed";
          statusBadge.innerHTML = "✓ Committed to Dataset";
        }
      });

      if (selectAllCheckbox) selectAllCheckbox.checked = false;

      // Update counters
      updateCounters();

      // Show celebratory success toast notification with link to reports
      showToast(
        "Repairs Applied Successfully",
        `Successfully committed ${count} approved corrections! Click here to view the certified Quality Report →`
      );

      console.log(`[DataFix] ${count} approved repairs committed to dataset cleanly.`);
    }, 1200);
  };

  if (repairToast) {
    repairToast.style.cursor = "pointer";
    repairToast.title = "Click to view certified report in Reports tab";
    repairToast.addEventListener("click", (e) => {
      if (!e.target.classList.contains("toast-close-btn")) {
        if (window.navigateToTab) window.navigateToTab("reports");
      }
    });
  }

  if (applyRepairsBtn) applyRepairsBtn.addEventListener("click", executeApplyRepairs);
  if (bottomApplyBtn) bottomApplyBtn.addEventListener("click", executeApplyRepairs);
}

/**
 * ==========================================================================
 * Data Quality Comparison Chart (Reports Page)
 * Before vs After quality dimensions breakdown
 * ==========================================================================
 */
function initQualityComparisonChart() {
  const ctx = document.getElementById("qualityComparisonChart");
  if (!ctx || typeof Chart === "undefined") return;

  window.qualityComparisonChartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels: [
        "Completeness (Nulls)",
        "Uniqueness (Duplicates)",
        "Validity (Formats)",
        "Consistency (Values)",
        "Conformity (Outliers)",
        "Overall Quality Index"
      ],
      datasets: [
        {
          label: "Original Score (%)",
          data: [89.4, 96.7, 93.6, 94.9, 97.0, 92.4],
          backgroundColor: "rgba(139, 92, 246, 0.8)", // Purple
          borderColor: "#191e2e",
          borderWidth: 1.5,
          borderRadius: 6,
          barPercentage: 0.7,
          categoryPercentage: 0.8
        },
        {
          label: "Final Repaired Score (%)",
          data: [99.8, 100.0, 99.7, 99.9, 99.1, 99.7],
          backgroundColor: "rgba(16, 185, 129, 0.9)", // Green
          borderColor: "#191e2e",
          borderWidth: 1.5,
          borderRadius: 6,
          barPercentage: 0.7,
          categoryPercentage: 0.8
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: "top",
          align: "end",
          labels: {
            color: "#94a3b8",
            usePointStyle: true,
            boxWidth: 8,
            font: { family: "'Plus Jakarta Sans', sans-serif", size: 12 }
          }
        },
        tooltip: {
          backgroundColor: "#191e2e",
          titleColor: "#f8fafc",
          bodyColor: "#94a3b8",
          borderColor: "#232a3e",
          borderWidth: 1,
          padding: 10,
          callbacks: {
            label: (item) => ` ${item.dataset.label}: ${item.raw}%`
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: "#94a3b8",
            font: { family: "'Plus Jakarta Sans', sans-serif", size: 11 }
          }
        },
        y: {
          min: 80,
          max: 100,
          grid: { color: "rgba(255, 255, 255, 0.04)" },
          ticks: {
            color: "#64748b",
            font: { family: "'Plus Jakarta Sans', sans-serif" },
            callback: (val) => `${val}%`
          }
        }
      }
    }
  });
}

/**
 * ==========================================================================
 * Reports Page Downloads & Artifact Generators
 * ==========================================================================
 */
function setupReportsPage() {
  const downloadReportBtn = document.getElementById("downloadReportBtn");
  const downloadCleanDatasetBtn = document.getElementById("downloadCleanDatasetBtn");
  const cardDownloadCleanBtn = document.getElementById("cardDownloadCleanBtn");
  const cardDownloadReportBtn = document.getElementById("cardDownloadReportBtn");

  // Helper to trigger direct browser file download
  const triggerBrowserDownload = (filename, content, mimeType) => {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 200);
  };

  // Generate Sample Cleaned CSV Dataset
  const handleDownloadCleanDataset = (button) => {
    const originalText = button.innerHTML;
    button.innerHTML = `
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
        <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
        <path d="M12 2a10 10 0 0 1 10 10"></path>
      </svg> Exporting Clean Dataset...
    `;
    button.disabled = true;

    setTimeout(() => {
      const csvData = [
        "row_id,transaction_id,customer_id,email,postal_code,state_code,amount_usd,currency,date_registered,status",
        "10482,TXN-98213-US,CUST-49102,not_provided@datafix.io,94105,CA,189.50,USD,2026-02-14,VERIFIED_CLEAN",
        "10490,TXN-98214-US-REV1,CUST-49118,sarah.connor@cyberdyne.com,10001,NY,450.00,USD,2026-02-14,VERIFIED_CLEAN",
        "10512,TXN-98215-US,CUST-49144,alex.murphy@omnicorp.org,90210,CA,72.25,USD,2026-02-15,VERIFIED_CLEAN",
        "10544,TXN-98216-US,CUST-49182,elena.rostova@globaltrade.net,98101,CA,1200.00,USD,2026-02-15,VERIFIED_CLEAN",
        "10578,TXN-98217-US,CUST-49201,david.bowie@stardust.co.uk,30301,GA,94280.00,USD,2026-02-16,WINSORIZED_CLEAN",
        "10601,TXN-98218-US,CUST-49245,clara.oswald@tardis.edu,02138,MA,310.80,USD,2026-02-28,VERIFIED_CLEAN",
        "10634,TXN-98219-US,CUST-49290,bruce.wayne@waynecorp.com,07101,NJ,9800.00,USD,2026-02-17,VERIFIED_CLEAN",
        "10670,TXN-98220-US,CUST-49312,diana.prince@themyscira.gov,20001,DC,55.00,USD,2026-02-18,VERIFIED_CLEAN"
      ].join("\n");

      triggerBrowserDownload("sales_transactions_q4_repaired_clean.csv", csvData, "text/csv;charset=utf-8;");

      button.innerHTML = "✓ Cleaned Dataset Downloaded";
      button.style.color = "#34d399";

      setTimeout(() => {
        button.innerHTML = originalText;
        button.disabled = false;
        button.style.color = "";
      }, 2500);
    }, 700);
  };

  // Generate Executive JSON Quality Report
  const handleDownloadQualityReport = (button) => {
    const originalText = button.innerHTML;
    button.innerHTML = `
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
        <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
        <path d="M12 2a10 10 0 0 1 10 10"></path>
      </svg> Generating Certificate...
    `;
    button.disabled = true;

    setTimeout(() => {
      const reportObject = {
        metadata: {
          platform: "DataFix - Autonomous Data Quality & Repair Engine",
          report_title: "Executive Data Quality & Remediation Certificate",
          certificate_id: "DF-CERT-2026-98412",
          generated_timestamp: new Date().toISOString(),
          engine_version: "2.4.0",
          compliance_standard: "ISO-8000 Certified Enterprise Grade"
        },
        dataset: {
          filename: "sales_transactions_q4.csv",
          total_records: 642800,
          total_attributes: 16,
          original_file_size: "42.8 MB",
          cleaned_file_size: "41.9 MB"
        },
        executive_summary: {
          original_data_quality_score: "92.4%",
          final_data_quality_score: "99.7%",
          quality_score_uplift: "+7.3%",
          total_errors_detected: 1824,
          total_errors_repaired: 1804,
          remaining_errors: 20,
          remediation_rate: "98.9%",
          production_readiness: "APPROVED"
        },
        problem_category_resolution: {
          missing_values: { detected: 684, repaired: 684, remaining: 0, resolution_pct: "100.0%" },
          duplicate_records: { detected: 210, repaired: 210, remaining: 0, resolution_pct: "100.0%" },
          invalid_data_formats: { detected: 412, repaired: 412, remaining: 0, resolution_pct: "100.0%" },
          inconsistent_values: { detected: 328, repaired: 328, remaining: 0, resolution_pct: "100.0%" },
          statistical_outliers: { detected: 190, repaired: 170, remaining: 20, resolution_pct: "89.5%" }
        },
        audit_signoff: {
          evaluator: "DataFix Autonomous Engine Daemon",
          checksum_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
          disposition: "Production Ready"
        }
      };

      triggerBrowserDownload(
        "DataFix_Quality_Audit_Report_Q4.json",
        JSON.stringify(reportObject, null, 2),
        "application/json;charset=utf-8;"
      );

      button.innerHTML = "✓ Audit Report Downloaded";
      button.style.color = "#34d399";

      setTimeout(() => {
        button.innerHTML = originalText;
        button.disabled = false;
        button.style.color = "";
      }, 2500);
    }, 700);
  };

  // Event Listeners for Header and Card Buttons
  if (downloadCleanDatasetBtn) {
    downloadCleanDatasetBtn.addEventListener("click", () => handleDownloadCleanDataset(downloadCleanDatasetBtn));
  }
  if (cardDownloadCleanBtn) {
    cardDownloadCleanBtn.addEventListener("click", () => handleDownloadCleanDataset(cardDownloadCleanBtn));
  }

  if (downloadReportBtn) {
    downloadReportBtn.addEventListener("click", () => handleDownloadQualityReport(downloadReportBtn));
  }
  if (cardDownloadReportBtn) {
    cardDownloadReportBtn.addEventListener("click", () => handleDownloadQualityReport(cardDownloadReportBtn));
  }
}

/**
 * Handlers for Platform Settings tab
 */
function setupSettingsTab() {
  const saveSettingsBtn = document.getElementById("saveSettingsBtn");

  if (saveSettingsBtn) {
    saveSettingsBtn.addEventListener("click", () => {
      saveSettingsBtn.textContent = "✓ Settings Saved";
      setTimeout(() => {
        saveSettingsBtn.textContent = "Save Configuration";
      }, 2000);
    });
  }
}
