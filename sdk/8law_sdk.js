// sdk/8law_sdk.js
// JavaScript SDK for 8law API (scaffold)
class EightLawClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
  }
  async getAnomalies(transactions) {
    const resp = await fetch(`${this.baseUrl}/anomalies`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(transactions)
    });
    return resp.json();
  }
  async predictTax(transactions) {
    const resp = await fetch(`${this.baseUrl}/predict_tax`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(transactions)
    });
    return resp.json();
  }
}
export default EightLawClient;
