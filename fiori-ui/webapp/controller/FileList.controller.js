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
        loading: true,
        error: "",
        hasError: false
      });
      this.getView().setModel(oModel, "files");

      this._loadFiles();
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
