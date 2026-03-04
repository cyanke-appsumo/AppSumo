import os
import sys
import datetime
import requests

# ── Credentials from environment ──────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
HUBSPOT_API_KEY   = os.environ["HUBSPOT_API_KEY"]
SLACK_BOT_TOKEN   = os.environ["SLACK_BOT_TOKEN"]
SLACK_CHANNEL_ID  = "G01C1A14J9W"  # #bd channel

# ── HubSpot helpers ────────────────────────────────────────────────────────────

def get_deals_created_today():
    """Return all deals created today (UTC)."""
    today = datetime.datetime.utcnow().date()
    start_ms = int(datetime.datetime(today.year, today.month, today.day,
                                     tzinfo=datetime.timezone.utc).timestamp() * 1000)
    end_ms   = start_ms + 86_400_000  # +24 hours

    url = "https://api.hubapi.com/crm/v3/objects/deals/search"
    headers = {
        "Authorization": f"Bearer {HUBSPOT_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "filterGroups": [{
            "filters": [
                {"propertyName": "createdate", "operator": "GTE", "value": str(start_ms)},
                {"propertyName": "createdate", "operator": "LT",  "value": str(end_ms)},
            ]
        }],
        "properties": ["dealname", "associations"],
        "limit": 100,
    }
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json().get("results", [])


def get_associated_company_id(deal_id):
    """Return the first associated company ID for a deal, or None."""
    url = f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}/associations/companies"
    headers = {"Authorization": f"Bearer {HUBSPOT_API_KEY}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        return None
    results = resp.json().get("results", [])
    return results[0]["id"] if results else None


def get_company_lead_score(company_id):
    """Return (company_name, lead_score) for the given company ID."""
    url = f"https://api.hubapi.com/crm/v3/objects/companies/{company_id}"
    headers = {"Authorization": f"Bearer {HUBSPOT_API_KEY}"}
    params  = {"properties": "name,lead_score"}
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    props = resp.json().get("properties", {})
    return props.get("name", "Unknown Company"), props.get("lead_score")


# ── Slack helper ───────────────────────────────────────────────────────────────

def post_to_slack(message):
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type":  "application/json",
    }
    payload = {"channel": SLACK_CHANNEL_ID, "text": message, "mrkdwn": True}
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack error: {data.get('error')}")


# ── Tier classification ────────────────────────────────────────────────────────

def classify(lead_score):
    """Return 'tier1', 'tier2', or 'no_score'."""
    if lead_score is None:
        return "no_score"
    try:
        score = int(float(lead_score))
    except (ValueError, TypeError):
        return "no_score"
    if score >= 70:
        return "tier1"
    return "tier2"


# ── Main ───────────────────────────────────────────────────────────────────────

def run_digest():
    today_label = datetime.datetime.utcnow().strftime("%B %d, %Y")
    print(f"[{today_label}] Starting daily deal digest...")

    deals = get_deals_created_today()
    print(f"  Found {len(deals)} deal(s) created today.")

    if not deals:
        post_to_slack(
            f"📊 *Daily Deal Digest — {today_label}*\n"
            "No new deals were created today."
        )
        print("Posted 'no deals' message to Slack.")
        return

    tier1, tier2, no_score = [], [], []

    for deal in deals:
        deal_id = deal["id"]
        company_id = get_associated_company_id(deal_id)
        if not company_id:
            no_score.append("(deal with no company)")
            continue
        company_name, lead_score = get_company_lead_score(company_id)
        bucket = classify(lead_score)
        if bucket == "tier1":
            tier1.append(company_name)
        elif bucket == "tier2":
            tier2.append(company_name)
        else:
            no_score.append(company_name)

    def fmt_list(items):
        return "\n".join(f"• {item}" for item in items) if items else "• —"

    message = (
        f"📊 *Daily Deal Digest — {today_label}*\n"
        f"*New Deals Created Today: {len(deals)}*\n\n"
        f"🥇 *Tier 1*\n{fmt_list(tier1)}\n\n"
        f"*Tier 2*\n{fmt_list(tier2)}\n\n"
        f"*No Score*\n{fmt_list(no_score)}"
    )

    post_to_slack(message)
    print("Digest posted to Slack successfully.")
    print(message)


if __name__ == "__main__":
    run_digest()
