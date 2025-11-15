sap.ui.define([
  "sap/ui/core/mvc/Controller",
  "sap/ui/model/json/JSONModel",
  "ewa/analyzer/model/config",
  "sap/m/FormattedText",
  "sap/m/Table",
  "sap/m/Column",
  "sap/m/ColumnListItem",
  "sap/m/Text"
], function (Controller, JSONModel, config, FormattedText, Table, Column, ColumnListItem, Text) {
  "use strict";

  return Controller.extend("ewa.analyzer.controller.Analysis", {
    onInit: function () {
      // Phase 1: no business logic yet
      var oModel = new JSONModel({
        file: null,
        content: "",
        html: "",
        sections: [],
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
          var aSections = this._buildSectionsFromMarkdown(sText);
          oModel.setProperty("/sections", aSections);
          oModel.setProperty("/html", this._markdownToHtml(sText));
          this._renderAnalysisContent(aSections);
          oModel.setProperty("/error", "");
        }.bind(this))
        .catch(function (err) {
          oModel.setProperty("/content", "");
          oModel.setProperty("/html", "");
          oModel.setProperty("/sections", []);
          oModel.setProperty("/error", err.message || "Failed to load analysis.");
          this._renderAnalysisContent([]);
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

    _renderAnalysisContent: function (aSections) {
      var oContainer = this.byId("analysisContent");
      if (!oContainer) {
        return;
      }

      oContainer.removeAllItems();

      if (!Array.isArray(aSections) || !aSections.length) {
        return;
      }

      var that = this;
      aSections.forEach(function (oSection) {
        if (!oSection || !oSection.markdown) {
          return;
        }

        var aBlocks = that._splitMarkdownIntoBlocks(oSection.markdown);
        aBlocks.forEach(function (oBlock) {
          if (!oBlock || !oBlock.lines || !oBlock.lines.length) {
            return;
          }

          if (oBlock.type === "table") {
            var oTableData = that._parseMarkdownTableLines(oBlock.lines);
            if (oTableData && oTableData.headers && oTableData.headers.length) {
              oContainer.addItem(that._createTableFromData(oTableData));
            }
          } else {
            var sHtml = that._markdownToHtml(oBlock.lines.join("\n"));
            if (sHtml) {
              oContainer.addItem(new FormattedText({ htmlText: sHtml }));
            }
          }
        });
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

    _createTableFromData: function (oData) {
      var oTable = new Table({ width: "100%" });

      (oData.headers || []).forEach(function (sHeader) {
        oTable.addColumn(new Column({
          header: new Text({ text: sHeader })
        }));
      });

      (oData.rows || []).forEach(function (aRow) {
        var aCells = [];
        for (var i = 0; i < oData.headers.length; i++) {
          var sCell = aRow[i] !== undefined ? aRow[i] : "";
          aCells.push(new Text({ text: sCell }));
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
