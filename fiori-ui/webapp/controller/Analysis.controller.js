sap.ui.define([
  "sap/ui/core/mvc/Controller",
  "sap/ui/model/json/JSONModel",
  "ewa/analyzer/model/config"
], function (Controller, JSONModel, config) {
  "use strict";

  return Controller.extend("ewa.analyzer.controller.Analysis", {
    onInit: function () {
      // Phase 1: no business logic yet
      var oModel = new JSONModel({
        file: null,
        content: "",
        loading: false,
        error: ""
      });
      this.getView().setModel(oModel, "analysis");
    },

    loadAnalysisForFile: function (oFile) {
      var oModel = this.getView().getModel("analysis");
      if (!oModel) {
        return;
      }

      oModel.setProperty("/file", oFile || null);
      oModel.setProperty("/content", "");
      oModel.setProperty("/error", "");
      oModel.setProperty("/loading", true);

      if (!oFile || !oFile.name) {
        oModel.setProperty("/loading", false);
        oModel.setProperty("/error", "No file selected for analysis.");
        return;
      }

      var sName = oFile.name;
      var iDot = sName.lastIndexOf(".");
      var sBase = iDot >= 0 ? sName.substring(0, iDot) : sName;
      var sBlobName = sBase + "_AI.md";
      var sUrl = config.apiUrl("/api/download/" + encodeURIComponent(sBlobName));

      fetch(sUrl)
        .then(function (response) {
          if (!response.ok) {
            return response.text().then(function (text) {
              var msg = text || ("Failed to load analysis: " + response.status);
              throw new Error(msg);
            });
          }
          return response.text();
        })
        .then(function (text) {
          oModel.setProperty("/content", text || "");
          oModel.setProperty("/error", "");
        })
        .catch(function (err) {
          oModel.setProperty("/content", "");
          oModel.setProperty("/error", err.message || "Failed to load analysis.");
        })
        .finally(function () {
          oModel.setProperty("/loading", false);
        });
    }
  });
});
