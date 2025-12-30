/**
 * SAP BTP Configuration Helper
 * 
 * This module provides configuration that adapts to the deployment environment:
 * - Local development: Uses hardcoded localhost URLs
 * - Azure Web Apps: Uses Azure backend URL
 * - SAP BTP: Uses relative URLs (App Router handles routing)
 * 
 * The App Router on BTP routes /api/* requests to the backend destination,
 * so the frontend only needs to use relative paths.
 */
sap.ui.define([], function () {
    "use strict";

    /**
     * Detect the current environment based on hostname
     */
    function detectEnvironment() {
        var hostname = window.location.hostname;
        
        // SAP BTP Cloud Foundry
        if (hostname.includes("hana.ondemand.com") || 
            hostname.includes("cfapps.") ||
            hostname.includes("applicationstudio")) {
            return "btp";
        }
        
        // Azure Web Apps
        if (hostname.includes("azurewebsites.net") || 
            hostname.includes("azure")) {
            return "azure";
        }
        
        // Local development
        return "local";
    }

    /**
     * Get the API base URL based on environment
     */
    function getApiBaseUrl() {
        var env = detectEnvironment();
        
        switch (env) {
            case "btp":
                // On BTP, App Router handles routing - use relative URLs
                return "";
            case "azure":
                // Azure Web Apps - use the configured backend URL
                return "https://sap-ewa-analyzer-backend.azurewebsites.net";
            case "local":
            default:
                // Local development
                return "http://localhost:8001";
        }
    }

    return {
        /**
         * Current environment: "btp", "azure", or "local"
         */
        environment: detectEnvironment(),

        /**
         * API base URL - empty string for BTP (relative URLs)
         */
        apiBaseUrl: getApiBaseUrl(),

        /**
         * API endpoints
         */
        endpoints: {
            listFiles: "/api/files",
            upload: "/api/upload",
            process: "/api/reprocess-ai",
            deleteAnalysis: "/api/delete-analysis",
            getAnalysis: "/api/download/",
            exportPdf: "/api/export-pdf-v2",
            exportPdfLegacy: "/api/export-pdf-enhanced",
            chat: "/api/chat",
            health: "/health"
        },

        /**
         * Get full endpoint URL
         * @param {string} key - Endpoint key from endpoints object
         * @returns {string} Full URL
         */
        getEndpoint: function (key) {
            return this.apiBaseUrl + this.endpoints[key];
        },

        /**
         * Get download URL for a specific blob
         * @param {string} blobName - Name of the blob to download
         * @returns {string} Full download URL
         */
        getDownloadUrl: function (blobName) {
            return this.apiBaseUrl + this.endpoints.getAnalysis + blobName;
        },

        /**
         * Check if running on SAP BTP
         * @returns {boolean}
         */
        isRunningOnBTP: function () {
            return this.environment === "btp";
        },

        /**
         * Check if running locally
         * @returns {boolean}
         */
        isLocal: function () {
            return this.environment === "local";
        },

        /**
         * Log current configuration (for debugging)
         */
        logConfig: function () {
            console.log("[BTP Config] Environment:", this.environment);
            console.log("[BTP Config] API Base URL:", this.apiBaseUrl || "(relative)");
        }
    };
});
