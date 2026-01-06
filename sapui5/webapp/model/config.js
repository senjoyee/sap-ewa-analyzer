sap.ui.define([], function () {
    "use strict";

    return {
        apiBaseUrl: "https://sap-ewa-analyzer-backend.azurewebsites.net",

        endpoints: {
            listFiles: "/api/files",
            upload: "/api/upload",
            process: "/api/reprocess-ai",
            deleteAnalysis: "/api/delete-analysis",
            getAnalysis: "/api/download/", // + blobName (for .md or .json)
            exportPdf: "/api/export-pdf-v2", // New JSON-based PDF export
            exportPdfLegacy: "/api/export-pdf-enhanced", // Legacy MD-based export
            exportExcel: "/api/export-excel", // Excel export
            chat: "/api/chat"
        },

        getEndpoint: function (key) {
            return this.apiBaseUrl + this.endpoints[key];
        },

        getDownloadUrl: function (blobName) {
            return this.apiBaseUrl + this.endpoints.getAnalysis + blobName;
        }
    };
});
