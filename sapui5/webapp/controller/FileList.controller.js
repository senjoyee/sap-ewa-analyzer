sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageToast",
    "sap/m/MessageBox",
    "ewa/analyzer/model/config"
], function (Controller, JSONModel, MessageToast, MessageBox, Config) {
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

        onUploadPress: function () {
            var oFileUploader = this.byId("fileUploader");
            var sCustomer = this.byId("customerInput").getValue();

            if (!oFileUploader.getValue()) {
                MessageToast.show("Please select a file first.");
                return;
            }

            if (!sCustomer) {
                MessageToast.show("Please enter a customer name.");
                return;
            }

            // Manually upload using fetch to handle FormData with customer name
            var oDomRef = oFileUploader.getDomRef("fu");
            var oFile = oDomRef.files[0];

            var formData = new FormData();
            formData.append("file", oFile);
            formData.append("customer_name", sCustomer);

            oFileUploader.setBusy(true);

            fetch(Config.getEndpoint("upload"), {
                method: "POST",
                body: formData
            })
                .then(response => {
                    if (response.ok) {
                        return response.json();
                    }
                    throw new Error("Upload failed");
                })
                .then(data => {
                    MessageToast.show("Upload successful");
                    oFileUploader.setValue("");
                    this.byId("customerInput").setValue("");
                    this._loadFiles();
                })
                .catch(err => {
                    MessageBox.error("Upload failed: " + err.message);
                })
                .finally(() => {
                    oFileUploader.setBusy(false);
                });
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
                    MessageBox.error("Processing failed: " + err.message);
                    this._loadFiles();
                });
        },

        onViewAnalysisPress: function (oEvent) {
            var oItem = oEvent.getSource().getBindingContext("files").getObject();
            var sBaseName = oItem.name.replace(".pdf", "");

            this.getOwnerComponent().getRouter().navTo("Preview", {
                baseName: sBaseName
            });
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
