sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageToast",
    "sap/m/MessageBox",
    "sap/m/Dialog",
    "sap/m/List",
    "sap/m/StandardListItem",
    "sap/m/TextArea",
    "sap/m/Button",
    "sap/m/VBox",
    "sap/m/HBox",
    "sap/m/Text",
    "sap/m/Title",
    "sap/m/Table",
    "sap/m/Column",
    "sap/m/ColumnListItem",
    "sap/m/Panel",
    "sap/m/Toolbar",
    "sap/ui/core/HTML",
    "sap/ui/core/Icon",
    "sap/m/CustomListItem",
    "sap/m/FormattedText",
    "sap/m/ObjectStatus",
    "sap/m/BusyIndicator",
    "sap/m/ScrollContainer",
    "sap/m/FlexItemData",
    "ewa/analyzer/model/config",
    "sap/m/ToolbarSpacer"
], function (Controller, JSONModel, MessageToast, MessageBox, Dialog, List, StandardListItem, TextArea, Button, VBox, HBox, Text, Title, Table, Column, ColumnListItem, Panel, Toolbar, HTML, Icon, CustomListItem, FormattedText, ObjectStatus, BusyIndicator, ScrollContainer, FlexItemData, Config, ToolbarSpacer) {
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
                chatHistory: [],
                chatBusy: false
            }), "analysis");

            this.getOwnerComponent().getRouter().getRoute("Preview").attachPatternMatched(this._onRouteMatched, this);
        },

        _onRouteMatched: function (oEvent) {
            var sBaseName = oEvent.getParameter("arguments").baseName;
            this._sBaseName = sBaseName;
            this._sBlobName = sBaseName + ".pdf";
            this._sJsonName = sBaseName + "_AI.json";
            this._sMdName = sBaseName + "_AI.md"; // Keep for chat context

            this._loadAnalysisJson(this._sJsonName);
        },

        _loadAnalysisJson: function (sJsonName) {
            var sUrl = Config.getDownloadUrl(sJsonName);
            var that = this;

            this.getView().setBusy(true);

            fetch(sUrl)
                .then(function (response) {
                    if (!response.ok) throw new Error("Analysis JSON not found");
                    return response.json();
                })
                .then(function (data) {
                    that._oAnalysisData = data;
                    that._renderFromJson(data);
                    that._extractMetadataFromJson(data);
                    // Also load MD for chat context (non-blocking)
                    that._loadMdForChat();
                })
                .catch(function (err) {
                    MessageBox.error("Failed to load analysis: " + err.message);
                })
                .finally(function () {
                    that.getView().setBusy(false);
                });
        },

        _loadMdForChat: function () {
            var sUrl = Config.getDownloadUrl(this._sMdName);
            var that = this;
            fetch(sUrl)
                .then(function (response) {
                    if (response.ok) return response.text();
                    return "";
                })
                .then(function (text) {
                    that._sDocumentContent = text;
                })
                .catch(function () {
                    // Fallback: stringify JSON for chat
                    that._sDocumentContent = JSON.stringify(that._oAnalysisData, null, 2);
                });
        },

        _extractMetadataFromJson: function (data) {
            var oModel = this.getView().getModel("analysis");
            var meta = data["System Metadata"] || data.system_metadata || {};

            oModel.setProperty("/title", meta["System ID"] || meta.system_id || this._sBaseName.replace(/_/g, " "));
            oModel.setProperty("/reportDate", meta["Report Date"] || meta.report_date || new Date().toLocaleDateString());
            oModel.setProperty("/analysisPeriod", meta["Analysis Period"] || meta.analysis_period || "");
            oModel.setProperty("/customer", meta["Customer"] || meta.customer || "");

            var sRisk = (data["Overall Risk"] || data.overall_risk || "low").toLowerCase();

            if (sRisk === "critical") {
                oModel.setProperty("/overallRisk", "Critical");
                oModel.setProperty("/riskState", "Error");
                oModel.setProperty("/riskIcon", "sap-icon://message-error");
            } else if (sRisk === "high") {
                oModel.setProperty("/overallRisk", "High");
                oModel.setProperty("/riskState", "Error");
                oModel.setProperty("/riskIcon", "sap-icon://message-error");
            } else if (sRisk === "medium") {
                oModel.setProperty("/overallRisk", "Medium");
                oModel.setProperty("/riskState", "Warning");
                oModel.setProperty("/riskIcon", "sap-icon://message-warning");
            } else {
                oModel.setProperty("/overallRisk", "Low");
                oModel.setProperty("/riskState", "Success");
                oModel.setProperty("/riskIcon", "sap-icon://message-success");
            }
        },

        // ═══════════════════════════════════════════════════════════════════════
        // JSON-BASED RENDERING (New approach - no Markdown parsing needed)
        // ═══════════════════════════════════════════════════════════════════════

        _renderFromJson: function (data) {
            var oContainer = this.byId("reportContainer");
            oContainer.destroyItems();

            var meta = data["System Metadata"] || data.system_metadata || {};
            var sid = meta["System ID"] || meta.system_id || "Unknown";
            var reportDate = this._formatDate(meta["Report Date"] || meta.report_date);
            var analysisPeriod = meta["Analysis Period"] || meta.analysis_period || "N/A";
            var overallRisk = data["Overall Risk"] || data.overall_risk || "Unknown";

            // Header
            oContainer.addItem(new Title({
                text: "EWA Analysis for " + sid + " (" + reportDate + ")",
                level: "H1"
            }).addStyleClass("sapUiMediumMarginBottom markdown-header-1"));

            // Analysis Period
            oContainer.addItem(new Text({
                text: "Analysis Period: " + analysisPeriod
            }).addStyleClass("sapUiTinyMarginBottom"));

            // Overall Risk
            this._renderRiskBadge(oContainer, overallRisk);

            // System Health Overview
            this._renderSystemHealth(oContainer, data);

            // Executive Summary
            this._renderExecutiveSummary(oContainer, data);

            // Positive Findings
            this._renderPositiveFindings(oContainer, data);

            // Key Findings & Recommendations
            this._renderKeyFindings(oContainer, data);

            // Capacity Outlook
            this._renderCapacityOutlook(oContainer, data);
        },

        _formatDate: function (sDate) {
            if (!sDate) return "N/A";
            // Normalize common formats to DD.MM.YYYY
            var isoMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(sDate);
            if (isoMatch) {
                return isoMatch[3] + "." + isoMatch[2] + "." + isoMatch[1];
            }
            var dotMatch = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(sDate);
            if (dotMatch) {
                return sDate;
            }
            var slashMatch = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(sDate);
            if (slashMatch) {
                return slashMatch[1] + "." + slashMatch[2] + "." + slashMatch[3];
            }
            // Fallback: Date parser, then format
            try {
                var d = new Date(sDate);
                if (!isNaN(d.getTime())) {
                    return d.toLocaleDateString("en-GB", { day: "2-digit", month: "2-digit", year: "numeric" });
                }
            } catch (e) { /* ignore */ }
            return sDate;
        },

        _renderRiskBadge: function (oContainer, sRisk) {
            var sRiskLower = sRisk.toLowerCase();
            var sRiskClass = "severity-chip-low";
            if (sRiskLower === "critical") sRiskClass = "severity-chip-critical";
            else if (sRiskLower === "high") sRiskClass = "severity-chip-high";
            else if (sRiskLower === "medium") sRiskClass = "severity-chip-medium";

            var sChipHtml = "<span class='severity-chip " + sRiskClass + "'>" + sRisk.toUpperCase() + "</span>";

            oContainer.addItem(new HBox({
                alignItems: "Center",
                items: [
                    new Title({ text: "Overall Risk Assessment:", level: "H3" }).addStyleClass("sapUiTinyMarginEnd"),
                    new HTML({ content: sChipHtml })
                ]
            }).addStyleClass("sapUiSmallMarginBottom sapUiMediumMarginTop"));
        },

        _renderSystemHealth: function (oContainer, data) {
            var health = data["System Health Overview"] || data.system_health_overview || {};
            if (!health || Object.keys(health).length === 0) return;

            oContainer.addItem(new Title({
                text: "System Health Overview",
                level: "H2"
            }).addStyleClass("sapUiMediumMarginTop sapUiSmallMarginBottom markdown-header-2"));

            var oTable = new Table({
                width: "100%",
                fixedLayout: false,
                columns: [
                    new Column({ header: new Text({ text: "Area" }) }),
                    new Column({ header: new Text({ text: "Status" }) })
                ]
            }).addStyleClass("analysis-table system-health-table");

            Object.keys(health).forEach(function (area) {
                var status = health[area];
                var sStatusClass = "";
                if (status && status.toLowerCase() === "good") sStatusClass = "status-good";
                else if (status && status.toLowerCase() === "fair") sStatusClass = "status-fair";
                else if (status && status.toLowerCase() === "poor") sStatusClass = "status-poor";

                var oStatusText = new Text({ text: status || "N/A" });
                if (sStatusClass) oStatusText.addStyleClass(sStatusClass);

                oTable.addItem(new ColumnListItem({
                    cells: [
                        new Text({ text: this._toTitleCase(area) }),
                        oStatusText
                    ]
                }));
            }.bind(this));

            oContainer.addItem(oTable);
        },

        _toTitleCase: function (str) {
            if (!str) return "";
            return str.replace(/\w\S*/g, function (txt) {
                return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
            });
        },

        _renderExecutiveSummary: function (oContainer, data) {
            var summary = data["Executive Summary"] || data.executive_summary || "";
            if (!summary) return;

            oContainer.addItem(new Title({
                text: "Executive Summary",
                level: "H2"
            }).addStyleClass("sapUiMediumMarginTop sapUiSmallMarginBottom markdown-header-2"));

            // Convert newlines to HTML
            var htmlContent = this._textToHtml(summary);
            oContainer.addItem(new HTML({
                content: "<div class='markdown-content executive-summary'>" + htmlContent + "</div>"
            }));
        },

        _textToHtml: function (text) {
            if (!text) return "";
            // Escape HTML
            var escaped = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
            // Convert **bold** to <strong>
            escaped = escaped.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
            // Render each non-empty line as a bullet (keeps executive summary compact)
            var lines = escaped.split("\n").map(function (line) { return line.trim(); }).filter(function (line) { return line.length > 0; });
            if (lines.length === 0) return "";
            var items = lines.map(function (line) {
                if (line.startsWith("- ") || line.startsWith("• ")) {
                    return "<li>" + line.substring(2) + "</li>";
                }
                return "<li>" + line + "</li>";
            });
            return "<ul>" + items.join("") + "</ul>";
        },

        _renderPositiveFindings: function (oContainer, data) {
            var findings = data["Positive Findings"] || data.positive_findings || [];
            if (!findings || findings.length === 0) return;

            oContainer.addItem(new Title({
                text: "Positive Findings",
                level: "H2"
            }).addStyleClass("sapUiMediumMarginTop sapUiSmallMarginBottom markdown-header-2"));

            // Get headers from first item
            var headers = Object.keys(findings[0]);
            var oTable = new Table({
                width: "100%",
                fixedLayout: false,
                popinLayout: "GridSmall"
            }).addStyleClass("analysis-table positive-findings-table");

            headers.forEach(function (h) {
                oTable.addColumn(new Column({
                    header: new Text({ text: h, wrapping: true }),
                    minScreenWidth: "Tablet",
                    demandPopin: true
                }));
            });

            findings.forEach(function (item) {
                var oCLI = new ColumnListItem();
                headers.forEach(function (h) {
                    oCLI.addCell(new Text({ text: item[h] || "N/A", wrapping: true }));
                });
                oTable.addItem(oCLI);
            });

            oContainer.addItem(oTable);
        },

        _renderKeyFindings: function (oContainer, data) {
            var findings = data["Key Findings"] || data.key_findings || [];
            var recommendations = data["Recommendations"] || data.recommendations || [];

            if (findings.length === 0 && recommendations.length === 0) return;

            oContainer.addItem(new Title({
                text: "Key Findings & Recommendations",
                level: "H2"
            }).addStyleClass("sapUiMediumMarginTop sapUiSmallMarginBottom markdown-header-2"));

            // Build recommendation lookup
            var recMap = {};
            recommendations.forEach(function (rec) {
                var linkedId = rec["Linked issue ID"] || rec.linked_issue_id;
                if (linkedId) {
                    if (!recMap[linkedId]) recMap[linkedId] = [];
                    recMap[linkedId].push(rec);
                }
            });

            // Group findings by severity
            var severityOrder = ["critical", "high", "medium", "low"];
            var severityGroups = { critical: [], high: [], medium: [], low: [] };
            var severityLabels = {
                critical: "Critical Issues",
                high: "High Priority Issues",
                medium: "Medium Priority Issues",
                low: "Low Priority Issues"
            };
            var severityIcons = {
                critical: "sap-icon://error",
                high: "sap-icon://warning2",
                medium: "sap-icon://hint",
                low: "sap-icon://information"
            };

            findings.forEach(function (finding) {
                var severity = (finding["Severity"] || finding.severity || "low").toLowerCase();
                if (!severityGroups[severity]) severity = "low";
                severityGroups[severity].push(finding);
            });

            // Render each severity group
            severityOrder.forEach(function (severity) {
                var groupFindings = severityGroups[severity];
                if (groupFindings.length === 0) return;

                // Create severity group panel
                var oGroupPanel = new Panel({
                    expandable: true,
                    expanded: false,
                    width: "auto",
                    headerToolbar: new Toolbar({
                        content: [
                            new Icon({
                                src: severityIcons[severity],
                                size: "1.25rem"
                            }).addStyleClass("sapUiSmallMarginEnd severity-icon-" + severity),
                            new Title({
                                text: severityLabels[severity] + " (" + groupFindings.length + ")",
                                level: "H3"
                            })
                        ]
                    })
                }).addStyleClass("sapUiSmallMarginBottom severityGroupPanel severityGroupPanel-" + severity);

                // Render findings within this group
                var oGroupContent = new VBox({ width: "100%" }).addStyleClass("sapUiSmallMarginTop");
                groupFindings.forEach(function (finding) {
                    var issueId = finding["Issue ID"] || finding.issue_id;
                    var linkedRecs = recMap[issueId] || [];
                    this._renderFindingPanelInGroup(oGroupContent, finding, linkedRecs, severity);
                }.bind(this));

                oGroupPanel.addContent(oGroupContent);
                oContainer.addItem(oGroupPanel);
            }.bind(this));
        },

        _formatIssueIdWithSeverity: function (issueId, severity) {
            var prefixMap = { critical: "C", high: "H", medium: "M", low: "L" };
            var sevKey = (severity || "low").toLowerCase();
            var prefix = prefixMap[sevKey] || "L";
            var base = issueId || "N/A";
            var match = String(base).match(/(\d+)/);
            var numberPart = match ? match[1] : base;
            return prefix + numberPart;
        },

        _renderFindingPanelInGroup: function (oContainer, finding, recommendations, severity) {
            var issueId = finding["Issue ID"] || finding.issue_id || "N/A";
            var area = finding["Area"] || finding.area || "General";
            var displayIssueId = this._formatIssueIdWithSeverity(issueId, severity);
            var findingText = finding["Finding"] || finding.finding || "";
            var impact = finding["Impact"] || finding.impact || "";
            var businessImpact = finding["Business impact"] || finding.business_impact || "";

            var oPanel = new Panel({
                expandable: true,
                expanded: false,
                width: "auto",
                headerToolbar: new Toolbar({
                    content: [
                        new Title({ text: displayIssueId, level: "H4" }).addStyleClass("sapUiSmallMarginBegin sapUiSmallMarginEnd"),
                        new HTML({ content: "<span class='area-badge'>" + area + "</span>" })
                    ]
                })
            }).addStyleClass("sapUiTinyMarginBottom findingPanelNested");

            // Build content
            var htmlContent = "";

            if (findingText) {
                htmlContent += "<div class='field-group'><strong>Finding:</strong><div>" + this._textToHtml(findingText) + "</div></div>";
            }
            if (impact) {
                htmlContent += "<div class='field-group'><strong>Impact:</strong><div>" + this._textToHtml(impact) + "</div></div>";
            }
            if (businessImpact) {
                htmlContent += "<div class='field-group'><strong>Business Impact:</strong><div>" + this._textToHtml(businessImpact) + "</div></div>";
            }

            // Add recommendations if linked
            recommendations.forEach(function (rec) {
                var action = rec["Action"] || rec.action || "";
                var preventative = rec["Preventative Action"] || rec.preventative_action || "";
                var effort = rec["Estimated Effort"] || rec.estimated_effort;
                var responsible = rec["Responsible Area"] || rec.responsible_area || "";

                if (action) {
                    htmlContent += "<div class='field-group'><strong>Action:</strong><div>" + this._textToHtml(action) + "</div></div>";
                }
                if (preventative) {
                    htmlContent += "<div class='field-group'><strong>Preventative Action:</strong><div>" + this._textToHtml(preventative) + "</div></div>";
                }
                if (effort) {
                    var effortText = typeof effort === "object"
                        ? "Analysis: " + (effort.analysis || "N/A") + ", Implementation: " + (effort.implementation || "N/A")
                        : effort;
                    htmlContent += "<div class='field-group'><strong>Estimated Effort:</strong> " + effortText + "</div>";
                }
                if (responsible) {
                    htmlContent += "<div class='field-group'><strong>Responsible Area:</strong> " + responsible + "</div>";
                }
            }.bind(this));

            oPanel.addContent(new HTML({ content: "<div class='finding-content'>" + htmlContent + "</div>" }));
            oContainer.addItem(oPanel);
        },

        _renderFindingPanelFromJson: function (oContainer, finding, recommendations) {
            var issueId = finding["Issue ID"] || finding.issue_id || "N/A";
            var area = finding["Area"] || finding.area || "General";
            var severity = (finding["Severity"] || finding.severity || "low").toLowerCase();
            var findingText = finding["Finding"] || finding.finding || "";
            var impact = finding["Impact"] || finding.impact || "";
            var businessImpact = finding["Business impact"] || finding.business_impact || "";

            var sSeverityClass = "severity-chip-low";
            if (severity === "critical") sSeverityClass = "severity-chip-critical";
            else if (severity === "high") sSeverityClass = "severity-chip-high";
            else if (severity === "medium") sSeverityClass = "severity-chip-medium";

            var sChipHtml = "<span class='severity-chip " + sSeverityClass + "'>" + severity.toUpperCase() + "</span>";

            var oPanel = new Panel({
                expandable: true,
                expanded: false,
                width: "auto",
                headerToolbar: new Toolbar({
                    content: [
                        new Title({ text: issueId, level: "H3" }).addStyleClass("sapUiSmallMarginBegin sapUiSmallMarginEnd"),
                        new HTML({ content: "<span class='area-badge'>" + area + "</span>" }),
                        new ToolbarSpacer(),
                        new HTML({ content: sChipHtml })
                    ]
                })
            }).addStyleClass("sapUiSmallMarginBottom findingPanel");

            // Build content
            var htmlContent = "";

            if (findingText) {
                htmlContent += "<div class='field-group'><strong>Finding:</strong><div>" + this._textToHtml(findingText) + "</div></div>";
            }
            if (impact) {
                htmlContent += "<div class='field-group'><strong>Impact:</strong><div>" + this._textToHtml(impact) + "</div></div>";
            }
            if (businessImpact) {
                htmlContent += "<div class='field-group'><strong>Business Impact:</strong><div>" + this._textToHtml(businessImpact) + "</div></div>";
            }

            // Add recommendations if linked
            recommendations.forEach(function (rec) {
                var action = rec["Action"] || rec.action || "";
                var preventative = rec["Preventative Action"] || rec.preventative_action || "";
                var effort = rec["Estimated Effort"] || rec.estimated_effort;
                var responsible = rec["Responsible Area"] || rec.responsible_area || "";

                if (action) {
                    htmlContent += "<div class='field-group'><strong>Action:</strong><div>" + this._textToHtml(action) + "</div></div>";
                }
                if (preventative) {
                    htmlContent += "<div class='field-group'><strong>Preventative Action:</strong><div>" + this._textToHtml(preventative) + "</div></div>";
                }
                if (effort) {
                    var effortText = typeof effort === "object"
                        ? "Analysis: " + (effort.analysis || "N/A") + ", Implementation: " + (effort.implementation || "N/A")
                        : effort;
                    htmlContent += "<div class='field-group'><strong>Estimated Effort:</strong> " + effortText + "</div>";
                }
                if (responsible) {
                    htmlContent += "<div class='field-group'><strong>Responsible Area:</strong> " + responsible + "</div>";
                }
            }.bind(this));

            oPanel.addContent(new HTML({ content: "<div class='finding-content'>" + htmlContent + "</div>" }));
            oContainer.addItem(oPanel);
        },

        _renderCapacityOutlook: function (oContainer, data) {
            var capacity = data["Capacity Outlook"] || data.capacity_outlook || {};
            if (!capacity || Object.keys(capacity).length === 0) return;

            oContainer.addItem(new Title({
                text: "Capacity Outlook",
                level: "H2"
            }).addStyleClass("sapUiMediumMarginTop sapUiSmallMarginBottom markdown-header-2"));

            var htmlContent = "<ul>";
            var fields = [
                { key: "Database Growth", label: "Database Growth" },
                { key: "CPU Utilization", label: "CPU Utilization" },
                { key: "Memory Utilization", label: "Memory Utilization" },
                { key: "Summary", label: "Capacity Summary" }
            ];

            fields.forEach(function (field) {
                var value = capacity[field.key] || "N/A";
                htmlContent += "<li><strong>" + field.label + ":</strong> " + value + "</li>";
            });

            htmlContent += "</ul>";
            oContainer.addItem(new HTML({
                content: "<div class='markdown-content capacity-outlook'>" + htmlContent + "</div>"
            }));
        },

        // ═══════════════════════════════════════════════════════════════════════
        // LEGACY MARKDOWN PARSING (Kept for backwards compatibility)
        // ═══════════════════════════════════════════════════════════════════════

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
                headerToolbar: new Toolbar({
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

        _chatMdToHtml: function (text) {
            if (!text) return "";

            var escapeHtml = function (s) {
                return (s || "")
                    .replace(/&/g, "&amp;")
                    .replace(/</g, "&lt;")
                    .replace(/>/g, "&gt;");
            };

            var renderInline = function (str) {
                return (str || "")
                    .replace(/`([^`]+)`/g, function (_, code) { return "<code>" + escapeHtml(code) + "</code>"; })
                    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
                    .replace(/\*(.*?)\*/g, "<em>$1</em>")
                    .replace(/\[(.+?)\]\((https?:[^\s)]+)\)/g, "<a href='$2' target='_blank'>$1</a>");
            };

            var lines = (text || "").split("\n");
            var htmlParts = [];
            var inList = false;
            var listTag = "ul";
            var inCode = false;
            var codeLines = [];

            var closeList = function () {
                if (inList) {
                    htmlParts.push("</" + listTag + ">");
                    inList = false;
                }
            };

            lines.forEach(function (line) {
                var rawLine = line || "";
                var trimmed = rawLine.trim();

                // Code fences
                if (trimmed.indexOf("```") === 0) {
                    closeList();
                    if (inCode) {
                        htmlParts.push("<pre><code>" + codeLines.join("\n") + "</code></pre>");
                        codeLines = [];
                        inCode = false;
                    } else {
                        inCode = true;
                    }
                    return;
                }

                if (inCode) {
                    codeLines.push(rawLine);
                    return;
                }

                // Horizontal rule
                if (/^(-{3,}|\*{3,})$/.test(trimmed)) {
                    closeList();
                    htmlParts.push("<hr>");
                    return;
                }

                // Headings (#, ##, ###)
                var headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/);
                if (headingMatch) {
                    closeList();
                    var level = headingMatch[1].length;
                    var headingText = renderInline(headingMatch[2]);
                    htmlParts.push("<p class='chatHeading h" + level + "'><strong>" + headingText + "</strong></p>");
                    return;
                }

                // Ordered / unordered lists
                var isUl = trimmed.indexOf("- ") === 0 || trimmed.indexOf("* ") === 0;
                var isOl = /^\d+\.\s+/.test(trimmed);
                if (isUl || isOl) {
                    var desiredTag = isOl ? "ol" : "ul";
                    if (!inList || listTag !== desiredTag) {
                        closeList();
                        listTag = desiredTag;
                        inList = true;
                        htmlParts.push("<" + listTag + ">");
                    }
                    var itemText = rawLine.replace(/^(-\s+|\*\s+|\d+\.\s+)/, "");
                    itemText = renderInline(itemText);
                    htmlParts.push("<li>" + itemText + "</li>");
                    return;
                }

                // Close list if we move out
                closeList();

                // Blank line -> spacer
                if (trimmed.length === 0) {
                    htmlParts.push("<br>");
                    return;
                }

                // Paragraph with inline markdown
                var paragraph = renderInline(rawLine);

                htmlParts.push("<p>" + paragraph + "</p>");
            });

            if (inCode) {
                htmlParts.push("<pre><code>" + escapeHtml(codeLines.join("\n")) + "</code></pre>");
            }

            if (inList) {
                htmlParts.push("</" + listTag + ">");
            }

            return htmlParts.join("");
        },

        _scrollChatToBottom: function () {
            if (this._oChatScroll && this._oChatScroll.scrollTo) {
                this._oChatScroll.scrollTo(0, 999999, 0);
            }
        },

        onNavBack: function () {
            this.getOwnerComponent().getRouter().navTo("Main");
        },

        onChatPress: function () {
            var oModel = this.getView().getModel("analysis");
            var aHistory = oModel.getProperty("/chatHistory") || [];

            aHistory.forEach(function (h) {
                if (h && !h.html) {
                    h.html = this._chatMdToHtml(h.content || "");
                }
            }.bind(this));
            oModel.refresh();

            if (!this._oChatDialog) {
                this._oChatList = new List("chatList", {
                    showNoData: false,
                    separators: "None",
                    items: {
                        path: "analysis>/chatHistory",
                        template: new CustomListItem({
                            content: [
                                new HBox({
                                    width: "100%",
                                    justifyContent: "End",
                                    visible: "{= ${analysis>role} === 'user' }",
                                    items: [
                                        new VBox({
                                            items: [
                                                new HTML({
                                                    content: "{analysis>html}",
                                                    sanitizeContent: false
                                                }).addStyleClass("chatFormattedText")
                                            ]
                                        }).addStyleClass("chatBubbleUser")
                                    ]
                                }).addStyleClass("chatMessageRow"),
                                new HBox({
                                    width: "100%",
                                    justifyContent: "Start",
                                    visible: "{= ${analysis>role} === 'assistant' }",
                                    items: [
                                        new VBox({
                                            items: [
                                                new HTML({
                                                    content: "{analysis>html}",
                                                    sanitizeContent: false
                                                }).addStyleClass("chatFormattedText")
                                            ]
                                        }).addStyleClass("chatBubbleBot")
                                    ]
                                }).addStyleClass("chatMessageRow"),
                                new HBox({
                                    width: "100%",
                                    justifyContent: "Start",
                                    visible: "{= ${analysis>role} === 'system' }",
                                    items: [
                                        new VBox({
                                            items: [
                                                new HTML({
                                                    content: "{analysis>html}",
                                                    sanitizeContent: false
                                                }).addStyleClass("chatFormattedText")
                                            ]
                                        }).addStyleClass("chatBubbleSystem")
                                    ]
                                }).addStyleClass("chatMessageRow")
                            ]
                        })
                    }
                }).addStyleClass("chatList");

                this._oChatScroll = new ScrollContainer({
                    height: "100%",
                    vertical: true,
                    horizontal: false,
                    content: [
                        this._oChatList
                    ]
                }).addStyleClass("chatScrollArea").setLayoutData(new FlexItemData({ growFactor: 1, minHeight: "0px" }));

                this._oChatBusyIndicator = new BusyIndicator({
                    text: "{i18n>chatThinking}",
                    visible: "{analysis>/chatBusy}",
                    size: "1rem"
                }).addStyleClass("chatBusyIndicator");

                this._oChatInput = new TextArea("chatInput", {
                    placeholder: "{i18n>chatPlaceholder}",
                    growing: true,
                    growingMaxLines: 6,
                    width: "100%",
                    enabled: "{= !${analysis>/chatBusy} }"
                }).addStyleClass("chatInput").setLayoutData(new FlexItemData({ growFactor: 1 }));

                this._oChatSendButton = new Button({
                    text: "{i18n>send}",
                    type: "Emphasized",
                    enabled: "{= !${analysis>/chatBusy} }",
                    press: this.onChatSend.bind(this)
                }).addStyleClass("chatSendButton");

                var oInputRow = new HBox({
                    width: "100%",
                    items: [
                        this._oChatInput,
                        this._oChatSendButton
                    ]
                }).addStyleClass("chatInputContainer");

                this._oChatInput.addEventDelegate({
                    onAfterRendering: function () {
                        var oDomRef = this._oChatInput.getDomRef();
                        if (oDomRef && !oDomRef.__chatKeyHandlerAttached) {
                            oDomRef.__chatKeyHandlerAttached = true;
                            oDomRef.addEventListener("keydown", function (e) {
                                if (e.key === "Enter" && !e.shiftKey) {
                                    e.preventDefault();
                                    this.onChatSend();
                                }
                            }.bind(this));
                        }
                    }.bind(this)
                });

                this._oChatDialog = new Dialog({
                    title: "{i18n>chatTitle}",
                    contentWidth: "560px",
                    contentHeight: "600px",
                    resizable: true,
                    draggable: true,
                    afterOpen: function () {
                        if (this._oChatInput) {
                            this._oChatInput.focus();
                        }
                        setTimeout(function () {
                            this._scrollChatToBottom();
                        }.bind(this), 0);
                    }.bind(this),
                    content: [
                        new VBox({
                            height: "100%",
                            justifyContent: "SpaceBetween",
                            items: [
                                this._oChatScroll,
                                new VBox({
                                    items: [
                                        this._oChatBusyIndicator,
                                        oInputRow
                                    ]
                                })
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
            setTimeout(function () {
                this._scrollChatToBottom();
            }.bind(this), 0);
        },


        onChatSend: function (oEvent) {
            var oModel = this.getView().getModel("analysis");
            if (oModel.getProperty("/chatBusy")) {
                return;
            }

            var sValue = "";
            if (oEvent && oEvent.getParameter) {
                sValue = oEvent.getParameter("value");
            }
            if (!sValue && this._oChatInput) {
                sValue = this._oChatInput.getValue();
            }

            sValue = (sValue || "").trim();
            if (!sValue) {
                return;
            }

            var aHistory = oModel.getProperty("/chatHistory") || [];
            aHistory.push({ role: "user", content: sValue, html: this._chatMdToHtml(sValue) });
            oModel.setProperty("/chatBusy", true);
            oModel.refresh();

            if (this._oChatInput) {
                this._oChatInput.setValue("");
                this._oChatInput.focus();
            }

            setTimeout(function () {
                this._scrollChatToBottom();
            }.bind(this), 0);

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
                .then(response => {
                    if (!response.ok) {
                        throw new Error("Chat request failed (" + response.status + ")");
                    }
                    return response.json();
                })
                .then(data => {
                    var sResponse = data.response || data.reply || data.message || "No response";
                    aHistory.push({ role: "assistant", content: sResponse, html: this._chatMdToHtml(sResponse) });
                    oModel.refresh();
                    setTimeout(function () {
                        this._scrollChatToBottom();
                    }.bind(this), 0);
                })
                .catch(err => {
                    var sErr = "Error: " + err.message;
                    aHistory.push({ role: "system", content: sErr, html: this._chatMdToHtml(sErr) });
                    oModel.refresh();
                    setTimeout(function () {
                        this._scrollChatToBottom();
                    }.bind(this), 0);
                })
                .finally(() => {
                    oModel.setProperty("/chatBusy", false);
                });
        }
    });
});
