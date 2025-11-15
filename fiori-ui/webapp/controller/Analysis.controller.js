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
        html: "",
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
      oModel.setProperty("/html", "");
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
          var sText = text || "";
          oModel.setProperty("/content", sText);
          oModel.setProperty("/html", this._markdownToHtml(sText));
          oModel.setProperty("/error", "");
        }.bind(this))
        .catch(function (err) {
          oModel.setProperty("/content", "");
          oModel.setProperty("/html", "");
          oModel.setProperty("/error", err.message || "Failed to load analysis.");
        })
        .finally(function () {
          oModel.setProperty("/loading", false);
        });
    },

    _markdownToHtml: function (sMarkdown) {
      if (!sMarkdown) {
        return "";
      }

      var sEscaped = this._escapeHtml(sMarkdown);
      var aLines = sEscaped.split(/\r?\n/);
      var aHtml = [];
      var bInList = false;

      aLines.forEach(function (line) {
        var sLine = line.trim();

        if (!sLine) {
          if (bInList) {
            aHtml.push("</ul>");
            bInList = false;
          }
          return;
        }

        var mHeading = sLine.match(/^(#{1,3})\s+(.*)$/);
        if (mHeading) {
          if (bInList) {
            aHtml.push("</ul>");
            bInList = false;
          }
          var iLevel = mHeading[1].length;
          var sText = mHeading[2];
          sText = sText.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
          var sTag = iLevel === 1 ? "h1" : (iLevel === 2 ? "h2" : "h3");
          aHtml.push("<" + sTag + ">" + sText + "</" + sTag + ">");
          return;
        }

        if (sLine.indexOf("- ") === 0 || sLine.indexOf("* ") === 0) {
          if (!bInList) {
            aHtml.push("<ul>");
            bInList = true;
          }
          var sItem = sLine.substring(2);
          sItem = sItem.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
          aHtml.push("<li>" + sItem + "</li>");
          return;
        }

        if (bInList) {
          aHtml.push("</ul>");
          bInList = false;
        }

        var sParagraph = sLine.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
        aHtml.push("<p>" + sParagraph + "</p>");
      });

      if (bInList) {
        aHtml.push("</ul>");
      }

      return aHtml.join("\n");
    },

    _escapeHtml: function (sText) {
      return String(sText)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }
  });
});
