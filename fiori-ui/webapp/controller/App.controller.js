sap.ui.define([
  "sap/ui/core/mvc/Controller"
], function (Controller) {
  "use strict";

  return Controller.extend("ewa.analyzer.controller.App", {
    onInit: function () {
      console.log("ewa.analyzer.controller.App onInit");
      // Default to showing the FileList page first
      var oApp = this.byId("app");
      if (oApp) {
        oApp.to(this.byId("fileListPageView"));
      }
    },

    navToFiles: function () {
      var oApp = this.byId("app");
      if (oApp) {
        oApp.to(this.byId("fileListPageView"));
      }
    },

    navToAnalysis: function () {
      var oApp = this.byId("app");
      if (oApp) {
        oApp.to(this.byId("analysisPageView"));
      }
    }
  });
});
