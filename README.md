# Tailscale GQL API

This is an under development GraphQL API for Tailscale's API v2 .

# Goals

* learn :)
* Be able to query a big fleet of tailscale nodes (with pagination and filters)
* Query for specific GQL types fast on an environment with very low resources
* Subscribe to patterns in order to monitor changes
* Monitor more than one tailscale network


# Future Goals

* Create a flexible Access Control GUI that uses device info for preview


Ideas and help are more than welcome as this is something I'm working only on my free Sundays.


# How to try

1) Download the repo
2) Install dependencies, I use pipenv: pipenv install
3) Pass the required env params: TAILNET_DOMAIN and API_KEY (You can get your api key from https://login.tailscale.com/admin/settings/keys)
4) Run the server:

    API_KEY="YOUR_API_KEY" TAILNET_DOMAIN="DOMAIN.COM" uvicorn main:app
5) Access the GQL browser: http://127.0.0.1:8000/graphql
