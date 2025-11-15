sap.ui.define([
  "sap/ui/core/mvc/Controller",
  "sap/ui/model/json/JSONModel",
  "ewa/analyzer/model/config"
], function (Controller, JSONModel, config) {
  "use strict";

  return Controller.extend("ewa.analyzer.controller.FileList", {
    onInit: function () {
      console.log("ewa.analyzer.controller.FileList onInit");

      var oModel = new JSONModel({
        files: [],
        allFiles: [],
        loading: true,
        error: "",
        hasError: false
      });
      this.getView().setModel(oModel, "files");

      this._loadFiles();
    },

    onViewAnalysisPress: function (oEvent) {
      var oButton = oEvent.getSource();
      var oContext = oButton && oButton.getBindingContext("files");
      var oFile = oContext && oContext.getObject();
      console.log("FileList onViewAnalysisPress", oFile);
      var oApp = this.getView().getParent();
      if (oApp && oApp.to) {
        oApp.to("analysisPageView");
      }
    },

    onSelectionChange: function (oEvent) {
      var oTable = oEvent.getSource();
      var iSelected = oTable.getSelectedItems().length;
      var bHasSelection = iSelected > 0;

      var oView = this.getView();
      var oProcessButton = oView.byId("processButton");
      var oDeleteButton = oView.byId("deleteButton");

      if (oProcessButton) {
        oProcessButton.setEnabled(bHasSelection);
      }
      if (oDeleteButton) {
        oDeleteButton.setEnabled(bHasSelection);
      }
    },

    onSearch: function (oEvent) {
      var oModel = this.getView().getModel("files");
      if (!oModel) {
        return;
      }

      var sQuery = oEvent.getParameter("query");
      if (sQuery === undefined) {
        sQuery = oEvent.getParameter("newValue");
      }
      sQuery = (sQuery || "").toLowerCase();

      var aAllFiles = oModel.getProperty("/allFiles") || [];
      if (!sQuery) {
        oModel.setProperty("/files", aAllFiles);
        return;
      }

      var aFiltered = aAllFiles.filter(function (file) {
        var sName = (file.name || "").toLowerCase();
        var sCustomer = (file.customer_name || "").toLowerCase();
        return sName.indexOf(sQuery) !== -1 || sCustomer.indexOf(sQuery) !== -1;
      });

      oModel.setProperty("/files", aFiltered);
    },

    onFilterPress: function () {
      // Placeholder for future filter dialog; no backend logic yet
      console.log("FileList onFilterPress - filters not implemented yet");
    },

    _loadFiles: function () {
      var oModel = this.getView().getModel("files");
      if (!oModel) {
        return;
      }

      oModel.setProperty("/loading", true);
      oModel.setProperty("/error", "");
      oModel.setProperty("/hasError", false);

      var sUrl = config.apiUrl("/api/files");
      fetch(sUrl)
        .then(function (response) {
          var contentType = response.headers.get("content-type") || "";
          if (contentType.indexOf("application/json") === -1) {
            return response.text().then(function (text) {
              if (text.indexOf("Proxy error") !== -1 || text.indexOf("<html") !== -1) {
                throw new Error("Backend server is not running or reachable.");
              }
              throw new Error("Unexpected response type: " + contentType);
            });
          }

          if (!response.ok) {
            return response.json().then(function (errData) {
              var msg = errData && (errData.detail || errData.message);
              throw new Error(msg || ("Failed to fetch files: " + response.status));
            });
          }

          return response.json();
        })
        .then(function (data) {
          var aFiles = []; 
          if (Array.isArray(data)) {
            aFiles = data;
          } else if (data && Array.isArray(data.files)) {
            aFiles = data.files;
          }

          // Add display-friendly date fields without altering backend data
          aFiles = aFiles.map(function (file) {
            var sUploadedDisplay = "";
            try {
              if (file.last_modified) {
                var oUploadedDate = new Date(file.last_modified);
                if (!isNaN(oUploadedDate.getTime())) {
                  sUploadedDisplay = oUploadedDate.toLocaleString();
                } else {
                  sUploadedDisplay = String(file.last_modified);
                }
              }
            } catch (e) {
              sUploadedDisplay = String(file.last_modified || "");
            }

            var sAnalysisDisplay = file.report_date_str || "";
            if (!sAnalysisDisplay && file.report_date) {
              try {
                var oAnalysisDate = new Date(file.report_date);
                if (!isNaN(oAnalysisDate.getTime())) {
                  sAnalysisDisplay = oAnalysisDate.toLocaleDateString();
                }
              } catch (e2) {
                // ignore and keep empty
              }
            }

            file.uploaded_on_display = sUploadedDisplay;
            file.analysis_date_display = sAnalysisDisplay || "";
            return file;
          });

          oModel.setProperty("/allFiles", aFiles);
          oModel.setProperty("/files", aFiles);
          oModel.setProperty("/hasError", false);
        })
        .catch(function (err) {
          console.error("Error fetching files:", err);
          oModel.setProperty("/files", []);
          oModel.setProperty("/error", err.message || "Failed to load files.");
          oModel.setProperty("/hasError", true);
        })
        .finally(function () {
          oModel.setProperty("/loading", false);
        });
    }
  });
});
