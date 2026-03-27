sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageBox",
    "sap/m/Button",
    "sap/m/VBox",
    "sap/m/HBox",
    "sap/m/Text",
    "sap/m/Title",
    "sap/m/Table",
    "sap/m/Column",
    "sap/m/ColumnListItem",
    "sap/ui/core/HTML",
    "sap/m/ObjectStatus",
    "ewa/analyzer/model/config"
], function (Controller, JSONModel, MessageBox, Button, VBox, HBox, Text, Title, Table, Column, ColumnListItem, HTML, ObjectStatus, Config) {
    "use strict";

    var DOMAIN_LABELS = {
        security: "Security",
        database: "Database",
        performance: "Performance",
        basis: "Basis / Technical",
        business: "Business",
        lifecycle: "Lifecycle Management"
    };

    return Controller.extend("ewa.analyzer.controller.Analysis", {

        onInit: function () {
            this.getView().setModel(new JSONModel({
                title: "",
                reportDate: ""
            }), "analysis");

            this.getOwnerComponent().getRouter().getRoute("Preview").attachPatternMatched(this._onRouteMatched, this);
        },

        _onRouteMatched: function (oEvent) {
            var sBaseName = oEvent.getParameter("arguments").baseName;
            this._sBaseName = sBaseName;
            this._sWorkbookName = sBaseName + "_workbook.xlsx";
            this._sPayloadName = sBaseName + "_workbook_payload.json";

            this._loadWorkbookPayload();
        },

        _loadWorkbookPayload: function () {
            var sUrl = Config.getDownloadUrl(this._sPayloadName);
            var that = this;

            this.getView().setBusy(true);

            fetch(sUrl)
                .then(function (response) {
                    if (!response.ok) throw new Error("Workbook payload not found (HTTP " + response.status + ")");
                    return response.json();
                })
                .then(function (data) {
                    that._renderWorkbookSummary(data);
                })
                .catch(function (err) {
                    MessageBox.error("Failed to load analysis results: " + err.message);
                })
                .finally(function () {
                    that.getView().setBusy(false);
                });
        },

        _renderWorkbookSummary: function (payload) {
            var oContainer = this.byId("reportContainer");
            oContainer.destroyItems();

            var aDomainResults = payload.domain_results || [];
            var aSupplemental = payload.supplemental_findings || [];

            var totalRed = 0, totalAmber = 0, totalFindings = 0, totalParams = 0;
            aDomainResults.forEach(function (dr) {
                var aF = dr.findings || [];
                totalFindings += aF.length;
                totalParams += (dr.parameters || []).length;
                aF.forEach(function (f) {
                    var s = (f.rag_status || "").toUpperCase();
                    if (s === "RED") { totalRed++; }
                    else if (s === "AMBER" || s === "YELLOW") { totalAmber++; }
                });
            });

            oContainer.addItem(new Title({
                text: "EWA Workbook Analysis",
                level: "H1"
            }).addStyleClass("sapUiMediumMarginBottom markdown-header-1"));

            var oStatsBar = new HBox({
                wrap: "Wrap",
                items: [
                    this._makeStat(String(totalRed), "Critical / RED", "Error"),
                    this._makeStat(String(totalAmber), "Warnings / AMBER", "Warning"),
                    this._makeStat(String(totalFindings), "Total Findings", "None"),
                    this._makeStat(String(totalParams), "Parameters", "None"),
                    this._makeStat(String(aSupplemental.length), "Cross-Domain", "Information")
                ]
            }).addStyleClass("sapUiMediumMarginBottom");
            oContainer.addItem(oStatsBar);

            oContainer.addItem(new Button({
                text: "Download EWA Workbook (.xlsx)",
                icon: "sap-icon://excel-attachment",
                type: "Emphasized",
                press: this.onDownloadWorkbook.bind(this)
            }).addStyleClass("sapUiSmallMarginBottom"));

            oContainer.addItem(new Title({
                text: "Findings by Domain",
                level: "H2"
            }).addStyleClass("sapUiSmallMarginTop sapUiTinyMarginBottom markdown-header-2"));

            var oTable = new Table({ width: "100%", fixedLayout: false }).addStyleClass("sapUiSmallMarginBottom");
            ["Domain", "RED", "AMBER", "GREEN", "Findings", "Parameters"].forEach(function (h) {
                oTable.addColumn(new Column({
                    header: new Text({ text: h, wrapping: false }),
                    minScreenWidth: "Tablet",
                    demandPopin: true
                }));
            });

            aDomainResults.forEach(function (dr) {
                var aF = dr.findings || [];
                var red = 0, amber = 0, green = 0;
                aF.forEach(function (f) {
                    var s = (f.rag_status || "").toUpperCase();
                    if (s === "RED") { red++; }
                    else if (s === "AMBER" || s === "YELLOW") { amber++; }
                    else { green++; }
                });
                var label = DOMAIN_LABELS[dr.domain] || dr.domain;
                var oCLI = new ColumnListItem();
                oCLI.addCell(new Text({ text: label }));
                oCLI.addCell(new ObjectStatus({ text: String(red), state: red > 0 ? "Error" : "None" }));
                oCLI.addCell(new ObjectStatus({ text: String(amber), state: amber > 0 ? "Warning" : "None" }));
                oCLI.addCell(new Text({ text: String(green) }));
                oCLI.addCell(new Text({ text: String(aF.length) }));
                oCLI.addCell(new Text({ text: String((dr.parameters || []).length) }));
                oTable.addItem(oCLI);
            });
            oContainer.addItem(oTable);

            if (aSupplemental.length > 0) {
                oContainer.addItem(new Title({
                    text: "Cross-Domain Supplemental Findings (" + aSupplemental.length + ")",
                    level: "H2"
                }).addStyleClass("sapUiSmallMarginTop sapUiTinyMarginBottom markdown-header-2"));

                var oSupTable = new Table({ width: "100%" }).addStyleClass("sapUiSmallMarginBottom");
                ["Severity", "Title", "Finding"].forEach(function (h) {
                    oSupTable.addColumn(new Column({
                        header: new Text({ text: h, wrapping: false }),
                        minScreenWidth: "Tablet",
                        demandPopin: true
                    }));
                });
                aSupplemental.forEach(function (sf) {
                    var sev = (sf.severity || sf.rag_status || "INFO").toUpperCase();
                    var sevState = (sev === "CRITICAL" || sev === "HIGH" || sev === "RED") ? "Error"
                        : (sev === "MEDIUM" || sev === "AMBER" || sev === "YELLOW") ? "Warning" : "None";
                    var oCLI2 = new ColumnListItem();
                    oCLI2.addCell(new ObjectStatus({ text: sev, state: sevState }));
                    oCLI2.addCell(new Text({ text: sf.title || sf.finding_title || "", wrapping: true }));
                    oCLI2.addCell(new Text({ text: sf.finding || sf.description || "", wrapping: true }));
                    oSupTable.addItem(oCLI2);
                });
                oContainer.addItem(oSupTable);
            }

            oContainer.addItem(new Button({
                text: "Download EWA Workbook (.xlsx)",
                icon: "sap-icon://excel-attachment",
                type: "Emphasized",
                press: this.onDownloadWorkbook.bind(this)
            }).addStyleClass("sapUiMediumMarginTop"));
        },

        _makeStat: function (sValue, sLabel, sState) {
            return new VBox({
                alignItems: "Center",
                items: [
                    new ObjectStatus({
                        text: sValue,
                        state: sState || "None"
                    }).addStyleClass("ewaStatValue"),
                    new Text({ text: sLabel }).addStyleClass("ewaStatLabel")
                ]
            }).addStyleClass("ewaStatCard sapUiSmallMarginEnd sapUiSmallMarginBottom");
        },

        onDownloadWorkbook: function () {
            window.open(Config.getDownloadUrl(this._sWorkbookName), "_blank");
        },

        onNavBack: function () {
            this.getOwnerComponent().getRouter().navTo("Main");
        }
    });
});
