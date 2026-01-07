sap.ui.define([], function () {
    "use strict";

    /**
     * Detect the runtime environment.
     * - "local": localhost development
     * - "azure": Azure Web Apps (sap-ewa-analyzer-backend.azurewebsites.net)
     * - "btp": SAP BTP Cloud Foundry (relative URLs via AppRouter)
     */
    function detectEnvironment() {
        var hostname = window.location.hostname;
        if (hostname === "localhost" || hostname === "127.0.0.1") {
            return "local";
        }
        if (hostname.indexOf("azurewebsites.net") !== -1) {
            return "azure";
        }
        // BTP: cfapps.*.hana.ondemand.com or custom domain
        if (hostname.indexOf("hana.ondemand.com") !== -1 || 
            hostname.indexOf("cfapps") !== -1) {
            return "btp";
        }
        // Default to BTP for unknown domains (assume deployed)
        return "btp";
    }

    var environment = detectEnvironment();

    // Base URL depends on environment
    var apiBaseUrl;
    switch (environment) {
        case "local":
            apiBaseUrl = "http://localhost:8001";
            break;
        case "azure":
            apiBaseUrl = "https://sap-ewa-analyzer-backend.azurewebsites.net";
            break;
        case "btp":
            // On BTP, AppRouter handles routing - use relative URLs
            apiBaseUrl = "";
            break;
        default:
            apiBaseUrl = "";
    }

    return {
        environment: environment,
        apiBaseUrl: apiBaseUrl,

        endpoints: {
            listFiles: "/api/files",
            upload: "/api/upload",
            process: "/api/reprocess-ai",
            deleteAnalysis: "/api/delete-analysis",
            getAnalysis: "/api/download/", // + blobName (for .md or .json)
            exportPdf: "/api/export-pdf-v2", // New JSON-based PDF export
            exportPdfLegacy: "/api/export-pdf-enhanced", // Legacy MD-based export
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
