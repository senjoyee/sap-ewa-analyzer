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

      var oUploadModel = new JSONModel({
        customer: "",
        error: ""
      });
      this.getView().setModel(oUploadModel, "upload");

      this._loadFiles();
    },

    onViewAnalysisPress: function (oEvent) {
      var oButton = oEvent.getSource();
      var oContext = oButton && oButton.getBindingContext("files");
      var oFile = oContext && oContext.getObject();
      console.log("FileList onViewAnalysisPress", oFile);
      var oApp = this.getView().getParent();
      if (oApp && oApp.to) {
        var oAppView = oApp.getParent && oApp.getParent();
        var sAnalysisPageId = oAppView && oAppView.createId && oAppView.createId("analysisPageView");

        if (sAnalysisPageId) {
          oApp.to(sAnalysisPageId);

          var oAnalysisView = sap.ui.getCore().byId(sAnalysisPageId);
          if (oAnalysisView && oAnalysisView.getController) {
            var oAnalysisController = oAnalysisView.getController();
            if (oAnalysisController && oAnalysisController.loadAnalysisForFile) {
              oAnalysisController.loadAnalysisForFile(oFile);
            }
          }
        }
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

    onProcessPress: function () {
      var oTable = this.byId("fileTable");
      var oFilesModel = this.getView().getModel("files");
      if (!oTable || !oFilesModel) {
        return;
      }

      var aSelectedItems = oTable.getSelectedItems();
      if (!aSelectedItems || !aSelectedItems.length) {
        return;
      }

      var aFiles = aSelectedItems.map(function (oItem) {
        var oCtx = oItem.getBindingContext("files");
        return oCtx && oCtx.getObject();
      }).filter(function (oFile) {
        return !!oFile && !!oFile.name;
      });

      if (!aFiles.length) {
        return;
      }

      oFilesModel.setProperty("/error", "");
      oFilesModel.setProperty("/hasError", false);
      oFilesModel.setProperty("/loading", true);

      var sUrl = config.apiUrl("/api/process-and-analyze");

      var aPromises = aFiles.map(function (oFile) {
        return fetch(sUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ blob_name: oFile.name })
        }).then(function (response) {
          if (!response.ok) {
            return response.json().catch(function () { return {}; }).then(function (errData) {
              var msg = errData && (errData.detail || errData.message);
              throw new Error(msg || ("Processing failed for " + oFile.name + ": " + response.status));
            });
          }
          return response.json().catch(function () { return {}; });
        });
      });

      Promise.all(aPromises)
        .then(function () {
          this._loadFiles();
        }.bind(this))
        .catch(function (err) {
          console.error("Error processing files:", err);
          oFilesModel.setProperty("/error", err.message || "Processing failed.");
          oFilesModel.setProperty("/hasError", true);
        })
        .finally(function () {
          oFilesModel.setProperty("/loading", false);
        });
    },

    onDeletePress: function () {
      var oTable = this.byId("fileTable");
      var oFilesModel = this.getView().getModel("files");
      if (!oTable || !oFilesModel) {
        return;
      }

      var aSelectedItems = oTable.getSelectedItems();
      if (!aSelectedItems || !aSelectedItems.length) {
        return;
      }

      var aFiles = aSelectedItems.map(function (oItem) {
        var oCtx = oItem.getBindingContext("files");
        return oCtx && oCtx.getObject();
      }).filter(function (oFile) {
        return !!oFile && !!oFile.name;
      });

      if (!aFiles.length) {
        return;
      }

      oFilesModel.setProperty("/error", "");
      oFilesModel.setProperty("/hasError", false);
      oFilesModel.setProperty("/loading", true);

      var sUrl = config.apiUrl("/api/delete-analysis");

      var aPromises = aFiles.map(function (oFile) {
        var sName = oFile.name;
        var iDot = sName.lastIndexOf(".");
        var sBase = iDot >= 0 ? sName.substring(0, iDot) : sName;

        return fetch(sUrl, {
          method: "DELETE",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            fileName: sName,
            baseName: sBase
          })
        }).then(function (response) {
          if (!response.ok) {
            return response.json().catch(function () { return {}; }).then(function (errData) {
              var msg = errData && (errData.detail || errData.message);
              throw new Error(msg || ("Delete failed for " + sName + ": " + response.status));
            });
          }
          return response.json().catch(function () { return {}; });
        });
      });

      Promise.all(aPromises)
        .then(function () {
          this._loadFiles();
        }.bind(this))
        .catch(function (err) {
          console.error("Error deleting analysis:", err);
          oFilesModel.setProperty("/error", err.message || "Delete failed.");
          oFilesModel.setProperty("/hasError", true);
        })
        .finally(function () {
          oFilesModel.setProperty("/loading", false);
        });
    },

    onUploadPress: function () {
      var oDialog = this.byId("uploadDialog");
      var oUploadModel = this.getView().getModel("upload");
      if (oUploadModel) {
        oUploadModel.setProperty("/customer", "");
        oUploadModel.setProperty("/error", "");
      }
      if (oDialog) {
        oDialog.open();
      }
    },

    onUploadDialogCancel: function () {
      var oDialog = this.byId("uploadDialog");
      if (oDialog) {
        oDialog.close();
      }
    },

    onUploadDialogUpload: function () {
      var oView = this.getView();
      var oFileUploader = this.byId("uploadFile");
      var oUploadModel = oView.getModel("upload");
      var oFilesModel = oView.getModel("files");

      if (!oFileUploader || !oUploadModel || !oFilesModel) {
        return;
      }

      var oFileInput = document.getElementById(oFileUploader.getId() + "-fu");
      var aFiles = oFileInput && oFileInput.files;
      if (!aFiles || !aFiles.length) {
        oUploadModel.setProperty("/error", "Please choose a file to upload.");
        return;
      }

      var sCustomer = (oUploadModel.getProperty("/customer") || "").trim();
      if (!sCustomer) {
        oUploadModel.setProperty("/error", "Please enter a customer name.");
        return;
      }

      oUploadModel.setProperty("/error", "");

      var oFile = aFiles[0];
      var oFormData = new FormData();
      oFormData.append("file", oFile);
      oFormData.append("customer_name", sCustomer);

      var sUrl = config.apiUrl("/api/upload");
      oFilesModel.setProperty("/loading", true);

      fetch(sUrl, {
        method: "POST",
        body: oFormData
      })
        .then(function (response) {
          if (!response.ok) {
            return response.json().catch(function () {
              return {};
            }).then(function (errData) {
              var msg = errData && (errData.detail || errData.message);
              throw new Error(msg || ("Upload failed: " + response.status));
            });
          }
          return response.json();
        })
        .then(function () {
          var oDialog = this.byId("uploadDialog");
          if (oDialog) {
            oDialog.close();
          }
          // Clear chosen file
          if (oFileUploader.clear) {
            oFileUploader.clear();
          }
          // Refresh file list
          this._loadFiles();
        }.bind(this))
        .catch(function (err) {
          console.error("Error uploading file:", err);
          oUploadModel.setProperty("/error", err.message || "Upload failed.");
        })
        .finally(function () {
          oFilesModel.setProperty("/loading", false);
        });
    },

    _formatDateTime: function (vDate) {
      try {
        var oDate = vDate instanceof Date ? vDate : new Date(vDate);
        if (isNaN(oDate.getTime())) {
          return "";
        }
        var dd = String(oDate.getDate()).padStart(2, "0");
        var mm = String(oDate.getMonth() + 1).padStart(2, "0");
        var yyyy = oDate.getFullYear();
        var hh = String(oDate.getHours()).padStart(2, "0");
        var min = String(oDate.getMinutes()).padStart(2, "0");
        return dd + "." + mm + "." + yyyy + " " + hh + ":" + min;
      } catch (e) {
        return "";
      }
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
          var that = this;
          aFiles = aFiles.map(function (file) {
            var sUploadedDisplay = "";
            try {
              if (file.last_modified) {
                sUploadedDisplay = that._formatDateTime(file.last_modified);
                if (!sUploadedDisplay) {
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
                  var dd = String(oAnalysisDate.getDate()).padStart(2, "0");
                  var mm = String(oAnalysisDate.getMonth() + 1).padStart(2, "0");
                  var yyyy = oAnalysisDate.getFullYear();
                  sAnalysisDisplay = dd + "." + mm + "." + yyyy;
                }
              } catch (e2) {
                // ignore and keep empty
              }
            }

            file.uploaded_on_display = sUploadedDisplay;
            file.analysis_date_display = sAnalysisDisplay || "";
            return file;
          }.bind(this));

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
