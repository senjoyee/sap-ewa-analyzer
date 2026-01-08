# Setting up a BTP Technical User for CI/CD

For a robust CI/CD pipeline, you should avoid using your personal SAP ID. Instead, set up a dedicated **Technical User** (Service Account). This ensures the pipeline continues to work even if you leave the organization or change passwords.

## Prerequisites
- Administrator access to your **SAP BTP Global Account** or **Subaccount**.
- Administrator access to your **Identity Authentication Service (IAS)** tenant (if applicable).

---

## Option 1: Using SAP Cloud Identity Services (Recommended)

If your BTP account is connected to a custom Identity Provider (IAS):

1.  **Log in to IAS Administration Console**
    - Go to `Users & Authorizations` > `User Management`.
    - Click **+ Add User**.
2.  **Create the Technical User**
    - **User Type**: System / Technical (if available) or Employee.
    - **E-Mail**: Use a distribution list or a dummy email (e.g., `cicd-deployer@yourdomain.com`).
    - **Name**: "CICD Deployer".
    - Set a strong, non-expiring password.
3.  **Assign to BTP**
    - Go to your **SAP BTP Cockpit**.
    - Navigate to **Security** > **Users**.
    - Add the new user (e-mail address) using the **Custom Identity Provider**.

## Option 2: Using Default IDP (SAP ID Service) / Trial Account

If you are on a Trial account or using the default SAP ID Service, you cannot easily create a "technical" user without a valid unique email address.

1.  **Create a new SAP Universal ID**
    - Register a new account with a dedicated email address (e.g., `dev-ops+project@gmail.com`).
2.  **Assign to BTP**
    - Go to **SAP BTP Cockpit**.
    - Navigate to **Security** > **Users**.
    - Add this new user.

---

## Assigning Permissions (Crucial Step)

The user (technical or personal) needs specific roles to deploy applications.

1.  **Global Roles (Optional)**
    - If the user needs to manage subaccounts, assign `Global Account Administrator`. (Usually not needed for pure deployment).

2.  **Subaccount Roles**
    - Go to **Security** > **Users**.
    - Assign the `Cloud Foundry Environment` specific roles if visible, but the most important part is at the **Space** level.

3.  **Cloud Foundry Space Roles (Required for Deployment)**
    - Navigate to your **Subaccount** > **Cloud Foundry** > **Spaces**.
    - Click on the **Space** you are deploying to (e.g., `dev` or `prod`).
    - Click **Members**.
    - Click **Add Member**.
    - Enter the email of the Technical User.
    - **Assign Role**: `Space Developer`.
    - *Note: `Space Developer` is required to push apps, bind services, and manage routes.*

---

## Configuring GitHub Secrets

Once the user is created and has the `Space Developer` role:

1.  Go to your GitHub Repository.
2.  **Settings** > **Secrets and variables** > **Actions**.
3.  Add the following secrets:
    *   `CF_USERNAME`: The email address of the technical user.
    *   `CF_PASSWORD`: The password for the technical user.
    *   `CF_API_ENDPOINT`: Your region's API endpoint (e.g., `https://api.cf.eu10.hana.ondemand.com`).
    *   `CF_ORG`: Your BTP Organization name (found in BTP Cockpit > Subaccount > Overview).
    *   `CF_SPACE`: The space name (e.g., `dev`).

## Troubleshooting Login

If your BTP account uses **SSO** (Single Sign-On) and you cannot use a password directly:
*   You **must** use a user from an Identity Provider (IAS) that supports password authentication, OR
*   Use the `--sso` passcode method, but this requires manual intervention and **cannot be automated** in CI/CD.
*   **Solution**: Ensure your Technical User is in an IDP that allows password-based authentication (like SAP IAS) and is NOT forced to use corporate SSO (MFA) if possible, or use a specific "Technical User" type in IAS which bypasses MFA policies if configured correctly.
