sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageToast",
    "sap/m/MessageBox",
    "sap/m/Dialog",
    "sap/m/List",
    "sap/m/StandardListItem",
    "sap/m/FeedInput",
    "sap/m/Button",
    "sap/m/VBox",
    "sap/m/HBox",
    "sap/m/Text",
    "sap/m/Title",
    "sap/m/Table",
    "sap/m/Column",
    "sap/m/ColumnListItem",
    "sap/m/Panel",
    "sap/ui/core/HTML",
    "sap/m/CustomListItem",
    "sap/m/ObjectStatus",
    "ewa/analyzer/model/config",
    "sap/m/ToolbarSpacer"
], function (Controller, JSONModel, MessageToast, MessageBox, Dialog, List, StandardListItem, FeedInput, Button, VBox, HBox, Text, Title, Table, Column, ColumnListItem, Panel, HTML, CustomListItem, ObjectStatus, Config, ToolbarSpacer) {
    "use strict";

    return Controller.extend("ewa.analyzer.controller.Analysis", {

        onInit: function () {
            this.getView().setModel(new JSONModel({
                title: "",
                reportDate: "",
                overallRisk: "Unknown",
                riskState: "None",
                riskIcon: "sap-icon://question-mark",
                analysisPeriod: "",
                customer: "",
                chatHistory: []
            }), "analysis");

            this.getOwnerComponent().getRouter().getRoute("Preview").attachPatternMatched(this._onRouteMatched, this);
        },

        _onRouteMatched: function (oEvent) {
            var sBaseName = oEvent.getParameter("arguments").baseName;
            this._sBaseName = sBaseName;
            this._sBlobName = sBaseName + ".pdf";
            this._sMdName = sBaseName + "_AI.md";

            this._loadAnalysis(this._sMdName);
        },

        _loadAnalysis: function (sMdName) {
            var sUrl = Config.getDownloadUrl(sMdName);

            this.getView().setBusy(true);

            fetch(sUrl)
                .then(response => {
                    if (!response.ok) throw new Error("Analysis not found");
                    return response.text();
                })
                .then(text => {
                    this._sDocumentContent = text;
                    this._parseAndRender(text);
                    this._extractMetadata(text);
                })
                .catch(err => {
                    MessageBox.error("Failed to load analysis: " + err.message);
                })
                .finally(() => {
                    this.getView().setBusy(false);
                });
        },

        _extractMetadata: function (text) {
            var oModel = this.getView().getModel("analysis");
            oModel.setProperty("/title", this._sBaseName.replace(/_/g, " "));
            oModel.setProperty("/reportDate", new Date().toLocaleDateString());

            if (text.match(/Critical/i)) {
                oModel.setProperty("/overallRisk", "Critical");
                oModel.setProperty("/riskState", "Error");
                oModel.setProperty("/riskIcon", "sap-icon://message-error");
            } else if (text.match(/High/i)) {
                oModel.setProperty("/overallRisk", "High");
                oModel.setProperty("/riskState", "Error");
                oModel.setProperty("/riskIcon", "sap-icon://message-error");
            } else if (text.match(/Medium/i)) {
                oModel.setProperty("/overallRisk", "Medium");
                oModel.setProperty("/riskState", "Warning");
                oModel.setProperty("/riskIcon", "sap-icon://message-warning");
            } else {
                oModel.setProperty("/overallRisk", "Low");
                oModel.setProperty("/riskState", "Success");
                oModel.setProperty("/riskIcon", "sap-icon://message-success");
            }
        },

        _parseAndRender: function (text) {
            var oContainer = this.byId("reportContainer");
            oContainer.destroyItems();

            var lines = text.split("\n");
            var currentBlock = { type: "text", content: [] };
            var inJsonBlock = false;
            var headerCount = 0;
            var currentSectionTitle = "";

            for (var i = 0; i < lines.length; i++) {
                var line = lines[i];

                // Ignore page breaks
                if (line.includes("<div style='page-break-before: always;'></div>")) {
                    continue;
                }

                // Header detection
                if (line.startsWith("#")) {
                    this._flushBlock(oContainer, currentBlock, currentSectionTitle);

                    // Special handling for "Executive Summary" -> Objective Card
                    if (line.includes("Executive Summary") || line.includes("Objective")) {
                        currentBlock = { type: "objective_card", title: line.replace(/^#+\s*/, "").trim(), content: [] };
                        continue;
                    }

                    var sId = "section_" + headerCount++;
                    var titleText = line.replace(/^#+\s*/, "").trim();
                    currentSectionTitle = titleText;

                    currentBlock = { type: "header", content: [line], id: sId };
                    this._flushBlock(oContainer, currentBlock, currentSectionTitle);
                    currentBlock = { type: "text", content: [] };
                    continue;
                }

                // JSON Block detection (for Key Findings)
                if (line.trim().startsWith("```json")) {
                    this._flushBlock(oContainer, currentBlock, currentSectionTitle);
                    inJsonBlock = true;
                    currentBlock = { type: "json", content: [] };
                    continue;
                }
                if (inJsonBlock && line.trim().startsWith("```")) {
                    inJsonBlock = false;
                    this._flushBlock(oContainer, currentBlock, currentSectionTitle);
                    currentBlock = { type: "text", content: [] };
                    continue;
                }
                if (inJsonBlock) {
                    currentBlock.content.push(line);
                    continue;
                }

                // Table detection
                if (line.trim().startsWith("|") && (lines[i + 1] && lines[i + 1].trim().startsWith("|"))) {
                    this._flushBlock(oContainer, currentBlock, currentSectionTitle);
                    currentBlock = { type: "table", content: [] };
                    while (i < lines.length && lines[i].trim().startsWith("|")) {
                        currentBlock.content.push(lines[i]);
                        i++;
                    }
                    i--;
                    this._flushBlock(oContainer, currentBlock, currentSectionTitle);
                    currentBlock = { type: "text", content: [] };
                    continue;
                }

                currentBlock.content.push(line);
            }
            this._flushBlock(oContainer, currentBlock, currentSectionTitle);
        },

        _flushBlock: function (oContainer, block, sSectionTitle) {
            if (!block || (block.content.length === 0 && block.type !== "header" && block.type !== "objective_card")) {
                return;
            }

            if (block.type === "objective_card") {
                // Render as a styled VBox (Card)
                var sDescription = block.content.join("\n");
                var htmlContent = this._simpleMdToHtml(sDescription);

                var oCard = new VBox({
                    width: "100%",
                    class: "objectiveCard sapUiMediumMarginBottom",
                    items: [
                        new HBox({
                            alignItems: "Center",
                            items: [
                                new VBox({
                                    items: [
                                        new Title({ text: block.title, level: "H2" }).addStyleClass("markdown-header-2"),
                                        new HTML({ content: "<div class='markdown-content'>" + htmlContent + "</div>" })
                                    ]
                                })
                            ]
                        })
                    ]
                });
                oContainer.addItem(oCard);
                return;
            }

            if (block.type === "header") {
                var level = block.content[0].match(/^#+/)[0].length;
                var text = block.content[0].replace(/^#+\s*/, "");
                var titleLevel = "H" + Math.min(level, 6);

                var oTitle = new Title({
                    text: text,
                    titleStyle: titleLevel,
                    wrapping: true
                }).addStyleClass("sapUiSmallMarginTop sapUiTinyMarginBottom markdown-header-" + level);

                if (block.id) {
                    oTitle.data("id", block.id);
                }

                oContainer.addItem(oTitle);

            } else if (block.type === "table") {
                oContainer.addItem(this._renderTable(block.content));

            } else if (block.type === "json") {
                try {
                    var jsonStr = block.content.join("\n");
                    var data = JSON.parse(jsonStr);

                    if (data.items && Array.isArray(data.items)) {
                        data.items.forEach(function (item) {
                            this._renderFindingPanel(oContainer, item);
                        }.bind(this));
                    }
                } catch (e) {
                    console.error("Failed to parse JSON block", e);
                    // Fallback: render as code block
                    oContainer.addItem(new HTML({
                        content: "<pre>" + block.content.join("\n") + "</pre>"
                    }));
                }

            } else {
                // Check for Overall Risk Assessment
                var sContent = block.content.join("\n");
                var riskMatch = sContent.match(/Overall Risk Assessment:\s*(.*)/i);

                if (riskMatch) {
                    var sRisk = riskMatch[1].trim().replace(/[`*]/g, ""); // Remove backticks and asterisks
                    var sRiskClass = "severity-chip-low";

                    if (sRisk.toLowerCase().includes("critical")) { sRiskClass = "severity-chip-critical"; }
                    else if (sRisk.toLowerCase().includes("high")) { sRiskClass = "severity-chip-high"; }
                    else if (sRisk.toLowerCase().includes("medium")) { sRiskClass = "severity-chip-medium"; }

                    var sRiskLabel = sRisk.charAt(0).toUpperCase() + sRisk.slice(1);
                    var sChipHtml = "<span class='severity-chip " + sRiskClass + "'>" + sRiskLabel + "</span>";

                    oContainer.addItem(new HBox({
                        alignItems: "Center",
                        items: [
                            new Title({ text: "Overall Risk Assessment:", level: "H3" }).addStyleClass("sapUiTinyMarginEnd"),
                            new HTML({ content: sChipHtml })
                        ]
                    }).addStyleClass("sapUiSmallMarginBottom"));
                    return;
                }

                // Text
                var html = block.content.join("\n");
                html = this._simpleMdToHtml(html);
                if (html.trim()) {
                    var sSectionClass = sSectionTitle ? "section-" + sSectionTitle.toLowerCase().replace(/[^a-z0-9]/g, "-") : "";
                    oContainer.addItem(new HTML({
                        content: "<div class='markdown-content " + sSectionClass + "'>" + html + "</div>",
                        sanitizeContent: true
                    }));
                }
            }
        },

        _renderFindingPanel: function (oContainer, item) {
            var sTitle = item.Finding || "Finding";
            var sSeverity = (item.Severity || "low").toLowerCase();

            var sSeverityClass = "severity-chip-low";
            if (sSeverity === "critical") { sSeverityClass = "severity-chip-critical"; }
            else if (sSeverity === "high") { sSeverityClass = "severity-chip-high"; }
            else if (sSeverity === "medium") { sSeverityClass = "severity-chip-medium"; }

            var sSeverityLabel = sSeverity.charAt(0).toUpperCase() + sSeverity.slice(1);
            var sChipHtml = "<span class='severity-chip " + sSeverityClass + "'>" + sSeverityLabel + "</span>";

            var oPanel = new Panel({
                expandable: true,
                expanded: false,
                width: "auto",
                headerToolbar: new sap.m.Toolbar({
                    content: [
                        new Title({ text: item["Issue ID"], level: "H3" }).addStyleClass("sapUiTinyMarginBegin"),
                        new HTML({ content: sChipHtml }).addStyleClass("sapUiMediumMarginBegin")
                    ]
                })
            }).addStyleClass("sapUiSmallMarginBottom");

            // Build content HTML
            var htmlContent = "";
            htmlContent += "<p><strong>Area:</strong> " + item.Area + "</p>"; // Add Area to content
            htmlContent += "<p><strong>" + item.Finding + "</strong></p>";

            if (item.Impact) htmlContent += "<p><strong>Impact:</strong> " + item.Impact + "</p>";
            if (item["Business impact"]) htmlContent += "<p><strong>Business Impact:</strong> " + item["Business impact"] + "</p>";
            if (item.Action) htmlContent += "<p><strong>Action:</strong> " + item.Action.replace(/\n/g, "<br>") + "</p>";

            oPanel.addContent(new HTML({ content: "<div class='markdown-content'>" + htmlContent + "</div>" }));
            oContainer.addItem(oPanel);
        },

        _renderTable: function (lines) {
            var headerLine = lines[0];
            var headers = headerLine.split("|").map(s => s.trim()).filter(s => s !== "");

            var oTable = new Table({
                width: "100%",
                fixedLayout: false,
                popinLayout: "GridSmall"
            }).addStyleClass("sapUiSmallMarginBottom");

            headers.forEach(h => {
                oTable.addColumn(new Column({
                    header: new Text({ text: h, wrapping: true }),
                    minScreenWidth: "Tablet",
                    demandPopin: true
                }));
            });

            for (var i = 2; i < lines.length; i++) {
                var rowLine = lines[i];
                var cells = rowLine.split("|").slice(1, -1).map(s => s.trim());

                if (cells.length > 0) {
                    var oCLI = new ColumnListItem();
                    cells.forEach(c => {
                        c = c.replace(/\*\*(.*?)\*\*/g, "$1");
                        oCLI.addCell(new Text({ text: c, wrapping: true }));
                    });
                    oTable.addItem(oCLI);
                }
            }
            return oTable;
        },

        _simpleMdToHtml: function (md) {
            var html = md;
            html = html.replace(/\*\*(.*?)\*\*/g, "<b>$1</b>");
            html = html.replace(/^- (.*)/gm, "<li>$1</li>");
            html = html.replace(/<\/li>\n/g, "</li>"); // Remove newline after list item to avoid <br>
            html = html.replace(/\n\n/g, "</p><p>");
            html = html.replace(/\n/g, "<br>");
            return "<p>" + html + "</p>";
        },

        onNavBack: function () {
            this.getOwnerComponent().getRouter().navTo("Main");
        },

        onChatPress: function () {
            if (!this._oChatDialog) {
                this._oChatDialog = new Dialog({
                    title: "{i18n>chatTitle}",
                    contentWidth: "500px",
                    contentHeight: "600px",
                    resizable: true,
                    draggable: true,
                    content: [
                        new VBox({
                            height: "100%",
                            justifyContent: "SpaceBetween",
                            items: [
                                new sap.m.ScrollContainer({
                                    height: "100%",
                                    vertical: true,
                                    horizontal: false,
                                    content: [
                                        new List("chatList", {
                                            showNoData: false,
                                            separators: "None",
                                            items: {
                                                path: "analysis>/chatHistory",
                                                template: new CustomListItem({
                                                    content: [
                                                        new HBox({
                                                            justifyContent: "Start",
                                                            width: "100%",
                                                            items: [
                                                                new VBox({
                                                                    items: [
                                                                        new Text({ text: "{analysis>content}" })
                                                                    ]
                                                                }).addStyleClass("{= ${analysis>role} === 'user' ? 'chatBubbleUser' : 'chatBubbleBot' }")
                                                            ]
                                                        }).addStyleClass("sapUiTinyMarginBottom")
                                                    ]
                                                })
                                            }
                                        })
                                    ]
                                }).setLayoutData(new sap.m.FlexItemData({ growFactor: 1, minHeight: "0px" })),

                                new FeedInput("chatInput", {
                                    post: this.onChatSend.bind(this),
                                    showIcon: false,
                                    placeholder: "{i18n>chatPlaceholder}",
                                    submit: this.onChatSend.bind(this)
                                }).addStyleClass("sapUiSmallMarginTop")
                            ]
                        })
                    ],
                    endButton: new Button({
                        text: "Close",
                        press: function () {
                            this._oChatDialog.close();
                        }.bind(this)
                    })
                });
                this.getView().addDependent(this._oChatDialog);
            }
            this._oChatDialog.open();
        },


        onChatSend: function (oEvent) {
            var sValue = oEvent.getParameter("value");
            var oModel = this.getView().getModel("analysis");
            var aHistory = oModel.getProperty("/chatHistory");

            aHistory.push({ role: "user", content: sValue });
            oModel.refresh();

            // Convert frontend format (role/content) to backend format (isUser/text)
            var backendHistory = aHistory.map(function (h) {
                return {
                    isUser: h.role === "user",
                    text: h.content
                };
            });

            var oPayload = {
                message: sValue,
                fileName: this._sBlobName,
                documentContent: this._sDocumentContent,
                chatHistory: backendHistory
            };

            fetch(Config.getEndpoint("chat"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(oPayload)
            })
                .then(response => response.json())
                .then(data => {
                    var sResponse = data.response || data.reply || data.message || "No response";
                    aHistory.push({ role: "assistant", content: sResponse });
                    oModel.refresh();
                })
                .catch(err => {
                    aHistory.push({ role: "system", content: "Error: " + err.message });
                    oModel.refresh();
                });
        }
    });
});
