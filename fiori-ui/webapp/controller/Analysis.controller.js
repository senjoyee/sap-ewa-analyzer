sap.ui.define([
  "sap/ui/core/mvc/Controller",
  "sap/ui/model/json/JSONModel",
  "ewa/analyzer/model/config",
  "sap/m/FormattedText",
  "sap/m/Table",
  "sap/m/Column",
  "sap/m/ColumnListItem",
  "sap/m/Text",
  "sap/m/Panel",
  "sap/m/VBox",
  "sap/m/ObjectStatus",
  "sap/uxap/ObjectPageSection",
  "sap/uxap/ObjectPageSubSection",
  "sap/ui/core/Icon"
], function (Controller, JSONModel, config, FormattedText, Table, Column, ColumnListItem, Text, Panel, VBox, ObjectStatus, ObjectPageSection, ObjectPageSubSection, Icon) {
  "use strict";

  return Controller.extend("ewa.analyzer.controller.Analysis", {
    onInit: function () {
      // Phase 1: no business logic yet
      var oModel = new JSONModel({
        file: null,
        content: "",
        html: "",
        sections: [],
        headerInfo: {
          title: "EWA Analysis",
          period: "",
          risk: "None",
          riskState: "None"
        },
        loading: false,
        error: ""
      });
      this.getView().setModel(oModel, "analysis");

      var oChatModel = new JSONModel({
        messages: [],
        input: "",
        loading: false,
        error: ""
      });
      this.getView().setModel(oChatModel, "chat");
    },

    loadAnalysisForFile: function (oFile) {
      var oModel = this.getView().getModel("analysis");
      if (!oModel) {
        return;
      }

      var oChatModel = this.getView().getModel("chat");
      if (oChatModel) {
        oChatModel.setData({
          messages: [],
          input: "",
          loading: false,
          error: ""
        });
      }

      oModel.setProperty("/file", oFile || null);
      oModel.setProperty("/content", "");
      oModel.setProperty("/html", "");
      oModel.setProperty("/sections", []);
      oModel.setProperty("/headerInfo", { title: "EWA Analysis", period: "", risk: "None", riskState: "None" });
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
          
          // Extract header info first
          var oHeaderInfo = this._extractHeaderInfo(sText);
          oModel.setProperty("/headerInfo", oHeaderInfo);

          var aSections = this._buildSectionsFromMarkdown(sText);
          oModel.setProperty("/sections", aSections);
          oModel.setProperty("/html", this._markdownToHtml(sText));
          this._renderObjectPageSections(aSections);
          oModel.setProperty("/error", "");
        }.bind(this))
        .catch(function (err) {
          oModel.setProperty("/content", "");
          oModel.setProperty("/html", "");
          oModel.setProperty("/sections", []);
          oModel.setProperty("/error", err.message || "Failed to load analysis.");
          this._renderObjectPageSections([]);
        }.bind(this))
        .finally(function () {
          oModel.setProperty("/loading", false);
        });
    },

    onOpenChat: function () {
      var oDialog = this.byId("chatDialog");
      if (oDialog) {
        oDialog.open();
      }
    },

    onCloseChat: function () {
      var oDialog = this.byId("chatDialog");
      if (oDialog) {
        oDialog.close();
      }
    },

    onChatSend: function () {
      var oView = this.getView();
      var oChatModel = oView.getModel("chat");
      var oAnalysisModel = oView.getModel("analysis");
      if (!oChatModel || !oAnalysisModel) {
        return;
      }

      var sMessage = (oChatModel.getProperty("/input") || "").trim();
      if (!sMessage) {
        return;
      }

      var oFile = oAnalysisModel.getProperty("/file");
      if (!oFile || !oFile.name) {
        oChatModel.setProperty("/error", "No file selected for chat.");
        return;
      }

      var aMessages = oChatModel.getProperty("/messages") || [];
      aMessages.push({ text: sMessage, isUser: true });
      oChatModel.setProperty("/messages", aMessages);
      oChatModel.setProperty("/input", "");
      oChatModel.setProperty("/error", "");
      oChatModel.setProperty("/loading", true);

      var sFileName = oFile.name;
      var sDocContent = oAnalysisModel.getProperty("/content") || "";
      var oBody = {
        message: sMessage,
        fileName: sFileName,
        documentContent: sDocContent,
        fileOrigin: "ui5-fiori",
        contentLength: sDocContent.length,
        chatHistory: aMessages.map(function (m) {
          return { text: m.text, isUser: !!m.isUser };
        })
      };

      var sUrl = config.apiUrl("/api/chat");

      fetch(sUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(oBody)
      })
        .then(function (response) {
          if (!response.ok) {
            return response.json().catch(function () { return {}; }).then(function (errData) {
              var msg = errData && (errData.detail || errData.message);
              throw new Error(msg || ("Chat request failed: " + response.status));
            });
          }
          return response.json();
        })
        .then(function (data) {
          var sResponseText = data && data.response ? String(data.response) : "";
          var aMsgs = oChatModel.getProperty("/messages") || [];
          if (sResponseText) {
            aMsgs.push({ text: sResponseText, isUser: false });
            oChatModel.setProperty("/messages", aMsgs);
          }
          if (data && data.error) {
            oChatModel.setProperty("/error", "The assistant reported an error in the response.");
          }
        })
        .catch(function (err) {
          console.error("Error in chat:", err);
          oChatModel.setProperty("/error", err.message || "Chat request failed.");
        })
        .finally(function () {
          oChatModel.setProperty("/loading", false);
        });
    },

    onNavBack: function () {
      var oView = this.getView();
      var oApp = oView.getParent();
      if (oApp && oApp.to) {
        var oAppView = oApp.getParent && oApp.getParent();
        var sFileListPageId = oAppView && oAppView.createId && oAppView.createId("fileListPageView");
        if (sFileListPageId) {
          oApp.to(sFileListPageId);
        }
      }
    },

    _extractHeaderInfo: function (sMarkdown) {
      var info = {
        title: "EWA Analysis",
        period: "",
        risk: "None",
        riskState: "None"
      };

      if (!sMarkdown) return info;

      var lines = sMarkdown.split("\n");
      // Look for title line
      var titleLine = lines.find(function(l) { return l.trim().indexOf("# EWA Analysis") === 0; });
      if (titleLine) {
        info.title = titleLine.replace("#", "").trim();
      }

      // Look for Period
      var periodLine = lines.find(function(l) { return l.indexOf("Analysis Period:") !== -1; });
      if (periodLine) {
        info.period = periodLine.split("Analysis Period:")[1].trim();
      }

      // Look for Risk
      var riskLine = lines.find(function(l) { return l.indexOf("Overall Risk Assessment:") !== -1; });
      if (riskLine) {
        var risk = riskLine.split("Overall Risk Assessment:")[1].trim().replace(/['"`]/g, "");
        info.risk = risk;
        // Map risk to state
        var r = risk.toLowerCase();
        if (r === "high" || r === "critical") info.riskState = "Error";
        else if (r === "medium" || r === "fair") info.riskState = "Warning";
        else if (r === "low" || r === "good") info.riskState = "Success";
        else info.riskState = "None";
      }

      return info;
    },

    _renderObjectPageSections: function (aSections) {
      var oPage = this.byId("analysisObjectPage");
      if (!oPage) {
        return;
      }

      oPage.destroySections();

      if (!Array.isArray(aSections) || !aSections.length) {
        return;
      }

      var that = this;
      aSections.forEach(function (oSection) {
        if (!oSection || !oSection.markdown) {
          return;
        }

        var sTitle = oSection.title || "Section";
        // Skip the main title if it's just the document title repetition
        if (sTitle.indexOf("EWA Analysis for") !== -1) {
            // But we still want the content if it has subsections like Executive Summary
            sTitle = "Overview";
        }

        var oSubSection = new ObjectPageSubSection({
          title: sTitle,
          blocks: []
        });

        // Specialized Rendering based on Section Title
        if (sTitle === "Key Findings & Recommendations") {
          var oCardData = that._parseKeyFindingsJson(oSection.markdown);
          if (oCardData) {
            oSubSection.addBlock(that._createKeyFindingsCards(oCardData));
          } else {
            // Fallback if JSON parsing fails
            that._addMarkdownBlocksToContainer(oSubSection, oSection.markdown, sTitle);
          }
        } else {
           that._addMarkdownBlocksToContainer(oSubSection, oSection.markdown, sTitle);
        }

        var oSectionControl = new ObjectPageSection({
          title: sTitle,
          subSections: [oSubSection]
        });

        oPage.addSection(oSectionControl);
      });
    },

    _addMarkdownBlocksToContainer: function(oContainer, sMarkdown, sSectionTitle) {
      var that = this;
      var aBlocks = that._splitMarkdownIntoBlocks(sMarkdown);
      
      aBlocks.forEach(function (oBlock) {
        if (!oBlock || !oBlock.lines || !oBlock.lines.length) {
          return;
        }

        if (oBlock.type === "table") {
          var oTableData = that._parseMarkdownTableLines(oBlock.lines);
          if (oTableData && oTableData.headers && oTableData.headers.length) {
             // Check if this looks like "System Health Overview"
             var bIsHealth = oTableData.headers[0] === "Area" && oTableData.headers[1] === "Status";
             // Check if this looks like KPI
             var bIsKPI = oTableData.headers.indexOf("Trend") !== -1;
             // Check if this is Positive Findings
             var bIsPositive = (sSectionTitle === "Positive Findings");

             oContainer.addBlock(that._createTableFromData(oTableData, bIsHealth, bIsKPI, bIsPositive));
          }
        } else {
           // Clean up header repetition in content
           var sText = oBlock.lines.join("\n");
           // If the block is just the title and header info we already extracted, we might want to skip or clean it?
           // For now, let's just render.
           var sHtml = that._markdownToHtml(sText);
           if (sHtml) {
             oContainer.addBlock(new FormattedText({ htmlText: sHtml }));
           }
        }
      });
    },

    _splitMarkdownIntoBlocks: function (sMarkdown) {
      var aLines = (sMarkdown || "").split(/\r?\n/);
      var aBlocks = [];
      var aCurrentText = [];
      var aCurrentTable = null;
      var bInTable = false;

      var pushText = function () {
        if (aCurrentText.length) {
          aBlocks.push({ type: "text", lines: aCurrentText.slice(0) });
          aCurrentText = [];
        }
      };

      var pushTable = function () {
        if (aCurrentTable && aCurrentTable.length) {
          aBlocks.push({ type: "table", lines: aCurrentTable.slice(0) });
        }
        aCurrentTable = null;
        bInTable = false;
      };

      for (var i = 0; i < aLines.length; i++) {
        var sLine = aLines[i] || "";
        var sTrim = sLine.trim();

        if (!bInTable) {
          var sNext = i + 1 < aLines.length ? (aLines[i + 1] || "").trim() : "";
          var bHeader = sTrim.indexOf("|") !== -1;
          var bSep = sNext.indexOf("|") !== -1 && sNext.indexOf("---") !== -1;

          if (bHeader && bSep) {
            pushText();
            bInTable = true;
            aCurrentTable = [];
            aCurrentTable.push(sTrim);
            aCurrentTable.push(sNext);
            i++;
            continue;
          }

          aCurrentText.push(sLine);
        } else {
          if (sTrim && sTrim.indexOf("|") !== -1) {
            aCurrentTable.push(sTrim);
          } else {
            pushTable();
            if (sTrim) {
              aCurrentText.push(sLine);
            }
          }
        }
      }

      if (bInTable) {
        pushTable();
      }
      if (aCurrentText.length) {
        aBlocks.push({ type: "text", lines: aCurrentText });
      }

      return aBlocks.filter(function (oBlock) {
        return oBlock.lines.some(function (ln) {
          return (ln || "").trim().length > 0;
        });
      });
    },

    _parseKeyFindingsJson: function (sMarkdown) {
      if (!sMarkdown) {
        return null;
      }

      var s = sMarkdown;
      var iStart = s.indexOf("```json");
      if (iStart === -1) {
        return null;
      }
      iStart += "```json".length;
      var iEnd = s.indexOf("```", iStart);
      if (iEnd === -1) {
        return null;
      }

      var sJson = s.substring(iStart, iEnd);
      try {
        var oData = JSON.parse(sJson);
        if (oData && oData.layout === "cards" && Array.isArray(oData.items)) {
          return oData;
        }
      } catch (e) {
        window.console && console.warn && console.warn("Failed to parse key findings JSON", e);
      }
      return null;
    },

    _createKeyFindingsCards: function (oCardData) {
      var aItems = oCardData.items || [];
      var oWrapper = new VBox({
        width: "100%",
        renderType: "Div",
        items: []
      });

      aItems.forEach(function (oItem) {
        var aInner = [];
        var sHeader = "";
        var sState = "None";
        var sIcon = "sap-icon://information";

        if (oItem["Issue ID"] || oItem.Area || oItem.Severity) {
          var sTitle = (oItem["Issue ID"] || "") + " - " + (oItem.Area || "");
          sHeader = sTitle;

          // Semantic coloring for header
          if (oItem.Severity) {
              var sSev = oItem.Severity.toLowerCase();
              if (sSev === "critical") {
                  sState = "Error";
                  sIcon = "sap-icon://error";
              } else if (sSev === "high") {
                  sState = "Error";
                  sIcon = "sap-icon://error";
              } else if (sSev === "medium") {
                  sState = "Warning";
                  sIcon = "sap-icon://alert";
              } else {
                  sState = "Success";
                  sIcon = "sap-icon://sys-enter";
              }
          }
        }

        if (oItem.Source) {
          aInner.push(new FormattedText({
            htmlText: "<p><strong>Source:</strong> " + this._escapeHtml(String(oItem.Source)) + "</p>"
          }));
        }

        if (oItem.Finding) {
          aInner.push(new FormattedText({ htmlText: this._markdownToHtml(String(oItem.Finding)) }));
        }

        if (oItem.Impact) {
          aInner.push(new FormattedText({
            htmlText: "<p><strong>Impact:</strong> " + this._escapeHtml(String(oItem.Impact)) + "</p>"
          }));
        }

        if (oItem["Business impact"]) {
          aInner.push(new FormattedText({
            htmlText: "<p><strong>Business impact:</strong> " + this._escapeHtml(String(oItem["Business impact"])) + "</p>"
          }));
        }

        if (oItem["Estimated Effort"] && (oItem["Estimated Effort"].analysis || oItem["Estimated Effort"].implementation)) {
          var oEff = oItem["Estimated Effort"];
          var sEff = "Analysis: " + (oEff.analysis || "n/a") + ", Implementation: " + (oEff.implementation || "n/a");
          aInner.push(new FormattedText({
            htmlText: "<p><strong>Estimated Effort:</strong> " + this._escapeHtml(sEff) + "</p>"
          }));
        }

        if (oItem["Responsible Area"]) {
          aInner.push(new FormattedText({
            htmlText: "<p><strong>Responsible Area:</strong> " + this._escapeHtml(String(oItem["Responsible Area"])) + "</p>"
          }));
        }

        if (oItem.Action) {
          aInner.push(new FormattedText({ htmlText: "<p><strong>Action:</strong></p>" + this._markdownToHtml(String(oItem.Action)) }));
        }

        if (oItem["Preventative Action"]) {
          aInner.push(new FormattedText({ htmlText: "<p><strong>Preventative Action:</strong></p>" + this._markdownToHtml(String(oItem["Preventative Action"])) }));
        }

        var oCardVBox = new VBox({
          width: "100%",
          class: "sapUiSmallMargin",
          items: aInner
        });
        
        // Create a Status for the Panel Header
        var oStatus = new ObjectStatus({
            text: oItem.Severity ? oItem.Severity.toUpperCase() : "INFO",
            state: sState,
            icon: sIcon,
            inverted: true
        });

        // Using a Toolbar for custom header content
        var oHeaderToolbar = new sap.m.Toolbar({
            design: "Transparent",
            content: [
                new sap.m.Title({ text: sHeader, titleStyle: "H5" }),
                new sap.m.ToolbarSpacer(),
                oStatus
            ]
        });

        oWrapper.addItem(new Panel({
          expandable: true,
          expanded: false,
          headerToolbar: oHeaderToolbar,
          width: "100%",
          content: [oCardVBox]
        }));
      }.bind(this));

      return oWrapper;
    },

    _parseMarkdownTableLines: function (aTableLines) {
      if (!Array.isArray(aTableLines) || aTableLines.length < 2) {
        return null;
      }

      var fnSplitRow = function (sRow) {
        var aParts = (sRow || "").split("|");
        if (aParts.length && !aParts[0].trim()) {
          aParts.shift();
        }
        if (aParts.length && !aParts[aParts.length - 1].trim()) {
          aParts.pop();
        }
        return aParts.map(function (s) {
          return s.trim();
        });
      };

      var aHeaders = fnSplitRow(aTableLines[0]);
      var sSep = (aTableLines[1] || "").trim();
      if (sSep.indexOf("---") === -1) {
        return null;
      }

      var aRows = [];
      for (var i = 2; i < aTableLines.length; i++) {
        var sLine = (aTableLines[i] || "").trim();
        if (!sLine) {
          continue;
        }
        var aCells = fnSplitRow(sLine);
        if (aCells.length) {
          aRows.push(aCells);
        }
      }

      return {
        headers: aHeaders,
        rows: aRows
      };
    },

    _createTableFromData: function (oData, bIsHealth, bIsKPI, bIsPositive) {
      var oTable = new Table({ width: "100%", backgroundDesign: "Transparent" });

      // Columns
      (oData.headers || []).forEach(function (sHeader) {
        oTable.addColumn(new Column({
          header: new Text({ text: sHeader })
        }));
      });

      // Rows
      (oData.rows || []).forEach(function (aRow) {
        var aCells = [];
        for (var i = 0; i < oData.headers.length; i++) {
          var sHeader = oData.headers[i];
          var sVal = aRow[i] !== undefined ? aRow[i] : "";
          var oControl = new Text({ text: sVal });

          if (bIsHealth && sHeader === "Status") {
             var sState = "None";
             var sLow = sVal.toLowerCase();
             if (sLow.indexOf("good") !== -1) sState = "Success";
             else if (sLow.indexOf("fair") !== -1) sState = "Warning";
             else if (sLow.indexOf("poor") !== -1) sState = "Error";
             else if (sLow.indexOf("critical") !== -1) sState = "Error";
             
             oControl = new ObjectStatus({
                 text: sVal,
                 state: sState,
                 inverted: true // Make it a badge
             });
          }
          else if (bIsKPI && sHeader === "Trend") {
              // Parse arrow
              var sIcon = "sap-icon://trend-up"; // default
              var sState = "None";
              
              // You might want to map arrow symbols to icons
              if (sVal.indexOf("→") !== -1) { sIcon = "sap-icon://measure"; sState = "None"; }
              else if (sVal.indexOf("↗") !== -1) { sIcon = "sap-icon://trend-up"; sState = "Success"; } // Assuming up is good? Context dependent.
              else if (sVal.indexOf("↘") !== -1) { sIcon = "sap-icon://trend-down"; sState = "Warning"; } 
              else if (sVal.indexOf("↓") !== -1) { sIcon = "sap-icon://trend-down"; sState = "Success"; } 
              
              // Since trend goodness is context dependent (response time down is good, users up is good), 
              // we'll just stick to neutral icons unless we parse the Area too.
              // Simple mapping for now:
              oControl = new ObjectStatus({
                  icon: sIcon
              });
          }
          else if (bIsPositive && i === 0) {
              // First column of Positive Findings: Area
              oControl = new ObjectStatus({
                  text: sVal,
                  state: "Success",
                  icon: "sap-icon://accept"
              });
          }

          aCells.push(oControl);
        }
        oTable.addItem(new ColumnListItem({ cells: aCells }));
      });

      return oTable;
    },

    _buildSectionsFromMarkdown: function (sMarkdown) {
      if (!sMarkdown) {
        return [];
      }

      var aLines = sMarkdown.split(/\r?\n/);
      var aSections = [];
      var sCurrentTitle = "Overview";
      var aCurrentLines = [];

      aLines.forEach(function (line) {
        var sTrim = (line || "").trim();

        // Skip explicit separators and page-break markers from backend markdown
        if (sTrim === "---" || sTrim.indexOf("<div style='page-break-before: always;'>") === 0) {
          return;
        }
        
        // Also skip the main title if we handle it in header
        if (sTrim.indexOf("# EWA Analysis") === 0) {
            return;
        }
        if (sTrim.indexOf("Analysis Period:") === 0) {
            return;
        }
        if (sTrim.indexOf("Overall Risk Assessment:") === 0) {
            return;
        }

        var mHeading = sTrim.match(/^##\s+(.*)$/);
        if (mHeading) {
          if (aCurrentLines.length) {
            aSections.push({
              title: sCurrentTitle,
              markdown: aCurrentLines.join("\n")
            });
          }
          sCurrentTitle = mHeading[1].trim() || sCurrentTitle;
          aCurrentLines = [];
        } else {
          aCurrentLines.push(line);
        }
      });

      if (aCurrentLines.length) {
        aSections.push({
          title: sCurrentTitle,
          markdown: aCurrentLines.join("\n")
        });
      }

      return aSections.filter(function (oSection) {
        return (oSection.markdown || "").trim().length > 0;
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
