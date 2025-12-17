sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/m/Panel",
    "sap/ui/core/HTML",
    "sap/m/CustomListItem",
    "sap/m/ObjectStatus",
    "ewa/analyzer/model/config",
    "sap/m/ToolbarSpacer",
    "sap/m/Select",
    "sap/ui/core/Item",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageToast",
    "sap/m/MessageBox"
], function (Controller, Panel, HTML, CustomListItem, ObjectStatus, Config, ToolbarSpacer, Select, Item, JSONModel, MessageToast, MessageBox) {
    "use strict";

    return Controller.extend("ewa.analyzer.controller.FileList", {

        formatter: {
            statusState: function (sStatus) {
                switch (sStatus) {
                    case "Analyzed":
                    case "completed":
                        return "Success";
                    case "Processing":
                    case "processing":
                        return "Warning";
                    case "Failed":
                    case "error":
                        return "Error";
                    default:
                        return "None";
                }
            },
            statusIcon: function (sStatus) {
                switch (sStatus) {
                    case "Analyzed":
                    case "completed":
                        return "sap-icon://accept";
                    case "Processing":
                    case "processing":
                        return "sap-icon://pending";
                    case "Failed":
                    case "error":
                        return "sap-icon://error";
                    default:
                        return "sap-icon://document";
                }
            }
        },

        onInit: function () {
            this.getView().setModel(new JSONModel([]), "files");
            this.getView().setModel(new JSONModel({ count: 0 }), "selectedFiles");
            this.getView().setModel(new JSONModel({ files: [] }), "uploadQueue");
            this.getView().setModel(new JSONModel({
                customers: [
                    { key: "TBS", text: "TBS" },
                    { key: "BSW", text: "BSW" },
                    { key: "SHOOSMITHS", text: "SHOOSMITHS" },
                    { key: "COREX", text: "COREX" },
                    { key: "SONOCO", text: "SONOCO" },
                    { key: "ASAHI", text: "ASAHI" }
                ]
            }), "customers");
            this._loadFiles();

            // Poll for updates every 10 seconds
            this._intervalId = setInterval(this._loadFiles.bind(this), 10000);
        },

        onExit: function () {
            if (this._intervalId) {
                clearInterval(this._intervalId);
            }
        },

        _loadFiles: function () {
            fetch(Config.getEndpoint("listFiles"))
                .then(response => response.json())
                .then(data => {
                    // Transform data to match UI model
                    var aFiles = (data.files || []).map(function (oFile) {
                        var sStatus = "New";

                        // Check processing flag first (takes priority)
                        if (oFile.processing) {
                            sStatus = "Processing";
                        } else if (oFile.ai_analyzed) {
                            sStatus = "Analyzed";
                        } else if (oFile.processed) {
                            sStatus = "Processing";
                        }

                        return {
                            name: oFile.name,
                            customer: oFile.customer_name,
                            status: sStatus, // "Analyzed", "Processing", "New"
                            uploadDate: oFile.last_modified ? new Date(oFile.last_modified) : null,
                            reportDate: oFile.report_date ? new Date(oFile.report_date) : null
                        };
                    });
                    this.getView().getModel("files").setData(aFiles);
                })
                .catch(err => console.error("Failed to load files", err));
        },

        onRefreshFiles: function () {
            this._loadFiles();
            MessageToast.show("Refreshing files...");
        },

        onFileChange: function () {
            var oFileUploader = this.byId("fileUploader");
            var oDomRef = oFileUploader.getDomRef("fu");
            var aFiles = Array.from(oDomRef && oDomRef.files ? oDomRef.files : []);

            // Cache actual File objects off-model to avoid serialization issues
            this._selectedFiles = aFiles;

            var sDefaultCustomer = this.byId("customerSelect").getSelectedKey();
            var aQueue = aFiles.map(function (oFile, idx) {
                return {
                    index: idx,
                    name: oFile.name,
                    size: oFile.size,
                    customer: sDefaultCustomer || ""
                };
            });

            this.getView().getModel("uploadQueue").setData({ files: aQueue });
        },

        onUploadPress: function () {
            var oFileUploader = this.byId("fileUploader");
            var sFallbackCustomer = this.byId("customerSelect").getSelectedKey();
            var aFiles = this._selectedFiles || [];

            if (!aFiles.length) {
                MessageToast.show("Please select at least one file.");
                return;
            }

            var aQueue = this.getView().getModel("uploadQueue").getProperty("/files") || [];
            var aMissingCustomer = aQueue.filter(function (q) {
                return !(q.customer || sFallbackCustomer);
            });
            if (aMissingCustomer.length) {
                MessageToast.show("Please select a customer for each file.");
                return;
            }

            oFileUploader.setBusy(true);

            Promise.allSettled(
                aFiles.map((oFile, idx) => {
                    var oQueueItem = aQueue.find(q => q.index === idx);
                    var sCustomer = oQueueItem && oQueueItem.customer ? oQueueItem.customer : sFallbackCustomer;

                    var formData = new FormData();
                    formData.append("file", oFile);
                    formData.append("customer_name", sCustomer);

                    return fetch(Config.getEndpoint("upload"), {
                        method: "POST",
                        body: formData
                    }).then(response => {
                        if (response.ok) {
                            return response.json();
                        }
                        return response.json()
                            .then(data => {
                                throw new Error(data.detail || "Upload failed");
                            })
                            .catch(() => {
                                throw new Error("Upload failed with status " + response.status);
                            });
                    });
                })
            )
                .then(results => {
                    var iSuccess = results.filter(r => r.status === "fulfilled").length;
                    var iFailed = results.length - iSuccess;

                    if (iSuccess > 0) {
                        MessageToast.show("Uploaded " + iSuccess + " file" + (iSuccess > 1 ? "s" : "") + " successfully");
                    }
                    if (iFailed > 0) {
                        MessageBox.error(iFailed + " file" + (iFailed > 1 ? "s" : "") + " failed to upload. Please check the console for details.");
                        console.error("Upload failures:", results.filter(r => r.status === "rejected").map(r => r.reason));
                    }

                    this._loadFiles();
                })
                .catch(err => {
                    MessageBox.error("Upload failed: " + err.message);
                })
                .finally(() => {
                    oFileUploader.setValue("");
                    oFileUploader.setBusy(false);
                });
        },

        onUploadQueueCustomerChange: function (oEvent) {
            var sKey = oEvent.getSource().getSelectedKey();
            var sPath = oEvent.getSource().getBindingContext("uploadQueue").getPath() + "/customer";
            this.getView().getModel("uploadQueue").setProperty(sPath, sKey);
        },

        onProcessPress: function (oEvent) {
            var oItem = oEvent.getSource().getBindingContext("files").getObject();
            this._processFile(oItem);
        },

        _processFile: function (oFile) {
            MessageToast.show("Processing started for " + oFile.name);

            // Optimistic update
            var oModel = this.getView().getModel("files");
            var aFiles = oModel.getData();
            var oFileInModel = aFiles.find(f => f.name === oFile.name);
            if (oFileInModel) {
                oFileInModel.status = "Processing";
                oModel.refresh();
            }

            fetch(Config.getEndpoint("process"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ blob_name: oFile.name })
            })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(data => {
                            throw new Error(data.detail || "Processing request failed");
                        }).catch(() => {
                            throw new Error(`Processing request failed with status ${response.status}`);
                        });
                    }
                    return response.json();
                })
                .then(data => {
                    console.log("Process response:", data);
                    if (data.success) {
                        MessageToast.show("Re-analysis completed successfully for " + oFile.name);
                    } else {
                        throw new Error(data.message || "Processing failed");
                    }
                    this._loadFiles(); // Refresh to get real status
                })
                .catch(err => {
                    console.error("Processing error:", err);
                    // "Failed to fetch" usually means timeout - refresh to check actual status
                    if (err.message === "Failed to fetch") {
                        MessageToast.show("Request timed out. Checking status...");
                        this._loadFiles();
                    } else {
                        MessageBox.error("Processing failed: " + err.message);
                        this._loadFiles();
                    }
                });
        },

        onViewAnalysisPress: function (oEvent) {
            var oItem = oEvent.getSource().getBindingContext("files").getObject();
            var sBaseName = oItem.name.replace(".pdf", "");

            this.getOwnerComponent().getRouter().navTo("Preview", {
                baseName: sBaseName
            });
        },

        onDownloadPress: function (oEvent) {
            var oItem = oEvent.getSource().getBindingContext("files").getObject();
            // The backend expects the AI-generated markdown file, not the original
            // Pattern: ERP_09_Nov_25.pdf -> ERP_09_Nov_25_AI.md
            var sBaseName = oItem.name.replace(".pdf", "");
            var sMdName = sBaseName + "_AI.md";

            // Construct the download URL
            // The backend expects blob_name as a query parameter
            var sUrl = Config.getEndpoint("exportPdf") + "?blob_name=" + encodeURIComponent(sMdName);

            // Trigger download in new window/tab
            window.open(sUrl, "_blank");
        },

        onDeletePress: function (oEvent) {
            var oItem = oEvent.getSource().getBindingContext("files").getObject();
            var sBaseName = oItem.name.replace(".pdf", "");

            MessageBox.confirm("Are you sure you want to delete " + oItem.name + "?", {
                onClose: (oAction) => {
                    if (oAction === MessageBox.Action.OK) {
                        fetch(Config.getEndpoint("deleteAnalysis"), {
                            method: "DELETE",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ fileName: oItem.name, baseName: sBaseName })
                        })
                            .then(response => {
                                if (response.ok) {
                                    MessageToast.show("Deleted successfully");
                                    this._loadFiles();
                                } else {
                                    throw new Error("Delete failed");
                                }
                            })
                            .catch(err => {
                                MessageBox.error("Delete failed: " + err.message);
                            });
                    }
                }
            });
        },

        onBatchProcessPress: function () {
            var aSelectedContexts = this.byId("filesTable").getSelectedContexts();
            if (aSelectedContexts.length === 0) {
                return;
            }

            aSelectedContexts.forEach(context => {
                var oFile = context.getObject();
                this._processFile(oFile);
            });

            this.byId("filesTable").removeSelections(true);
        },

        onBatchDeletePress: function () {
            var aSelectedContexts = this.byId("filesTable").getSelectedContexts();
            if (aSelectedContexts.length === 0) {
                return;
            }

            MessageBox.confirm("Delete " + aSelectedContexts.length + " files?", {
                onClose: (oAction) => {
                    if (oAction === MessageBox.Action.OK) {
                        aSelectedContexts.forEach(context => {
                            var oFile = context.getObject();
                            // Reuse delete logic (simplified for batch here)
                            var sBaseName = oFile.name.replace(".pdf", "");
                            fetch(Config.getEndpoint("deleteAnalysis"), {
                                method: "DELETE",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({ fileName: oFile.name, baseName: sBaseName })
                            }).then(() => this._loadFiles());
                        });
                        this.byId("filesTable").removeSelections(true);
                    }
                }
            });
        },

        onSelectionChange: function (oEvent) {
            var oTable = oEvent.getSource();
            var iSelectedCount = oTable.getSelectedItems().length;
            this.getView().getModel("selectedFiles").setProperty("/count", iSelectedCount);
        }
    });
});
