# Peppol / E-faktura

Varuflow supports electronic invoicing via Peppol BIS Billing 3.0 (Sweden) and EHF 3.0 (Norway). These are the standard e-invoice formats mandated for B2G (business-to-government) in both countries and increasingly common in B2B.

---

## Overview

| Format | Standard | Used in | Requirement |
|--------|----------|---------|-------------|
| Peppol BIS Billing 3.0 | UBL 2.1 XML | Sweden, EU | B2G mandatory (SE), voluntary B2B |
| EHF 3.0 | Norwegian UBL profile | Norway | Public sector standard near-mandatory |

---

## Peppol (Sweden)

### Feature Gating

Peppol export is a **PRO plan** feature. FREE-plan orgs see the button but get a 402 upgrade prompt.

### How to Export a Peppol Invoice

1. Open an invoice that is in SENT or PAID status
2. Click **Export Peppol XML** on the invoice detail page
3. `POST /api/einvoice/peppol/:id` — generates and returns UBL 2.1 XML
4. Download the `.xml` file
5. Submit via your AP (Access Point) provider to the Peppol network

### Validation

Click **Validate Peppol XML** to submit the generated XML to the SFTI (Swedish public sector e-invoice standard body) public validator:

```
POST /api/einvoice/peppol/:id/validate
```

Returns validation results with rule IDs and error messages. The XML must pass validation before submitting to the Peppol network.

### Swedish VAT Requirements

The Peppol exporter enforces Swedish VAT format:

```
SE + 12 digits (no separators)
Example: SE556123456701
```

The org's `vat_number` is validated and reformatted before embedding in the XML. Invoices with a missing or malformed VAT number will return a 422 error.

### Peppol BIS 3.0 XML Structure

The generated XML follows UBL 2.1 Invoice schema:

```xml
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:CustomizationID>urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0</cbc:CustomizationID>
  <cbc:ProfileID>urn:fdc:peppol.eu:2017:poacc:billing:01:1.0</cbc:ProfileID>
  <cbc:ID><!-- invoice number --></cbc:ID>
  <cbc:IssueDate><!-- YYYY-MM-DD --></cbc:IssueDate>
  <cbc:DueDate><!-- YYYY-MM-DD --></cbc:DueDate>
  <cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode>  <!-- 380 = commercial invoice -->
  ...
  <cac:AccountingSupplierParty>...</cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty>...</cac:AccountingCustomerParty>
  <cac:TaxTotal>...</cac:TaxTotal>
  <cac:LegalMonetaryTotal>...</cac:LegalMonetaryTotal>
  <cac:InvoiceLine>...</cac:InvoiceLine>
</Invoice>
```

---

## EHF 3.0 (Norway)

Norwegian EHF (Elektronisk HandelsFormat) 3.0 export is available for all plans.

### How to Export

```
GET /api/invoicing/invoices/:id/ehf
```

Returns the EHF 3.0 XML file as a download. No separate validation endpoint — use the [DIFI validator](https://vefa.difi.no/validator/) to validate before submission.

### Submission

Submit via your Norwegian PEPPOL Access Point (AP). Common Norwegian AP providers:

- Basware
- Pagero
- Xpedient
- Visma

---

## Access Point (AP) Integration

Varuflow generates the XML files. Submission to the Peppol network requires an **Access Point** — a certified gateway service. Varuflow does not currently have a built-in AP connector.

**Workflow:**

1. Generate XML in Varuflow (download or API)
2. Upload to your AP provider's portal or API
3. AP delivers to recipient via Peppol network

**Future:** Direct AP integration is on the roadmap (top requested feature from Swedish B2G customers).

---

## Country Configuration

Country-level Peppol settings are in `backend/config/countries/`:

```json
// SE.json
{
  "peppol": {
    "mandatory_b2g": true,
    "voluntary_b2b": true,
    "network_id": "0007",          // Swedish org number network
    "vat_prefix": "SE",
    "vat_digits": 12
  }
}

// NO.json
{
  "peppol": {
    "mandatory_b2g": true,
    "voluntary_b2b": false,
    "network_id": "0192",          // Norwegian org number network
    "format": "EHF3"
  }
}
```

---

## Legal Requirements (Sweden)

Swedish law (based on EU Directive 2014/55/EU) requires:

- All invoices to **central government** must be sent as Peppol BIS Billing 3.0
- Regional/municipal requirements vary — most require Peppol since 2021
- Private B2B: voluntary but increasingly expected by larger buyers

Reference: [Digg.se e-faktura](https://www.digg.se/e-legitimation-och-e-underskrift/e-faktura)

---

## Legal Requirements (Norway)

Norwegian law (EHF requirement):

- All invoices to the **Norwegian public sector** must be sent as EHF 3.0
- Private B2B: voluntary

Reference: [Anskaffelser.no e-faktura](https://www.anskaffelser.no/it/systemkrav-og-standarder/efaktura)
