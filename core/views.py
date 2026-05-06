from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from clients.models import Client, DeclarationStatus


@login_required
def home(request):
    total_clients = Client.objects.filter(active=True).count()
    context = {
        "total_clients": total_clients,
        "pending_clients": Client.objects.filter(active=True, tax_status=DeclarationStatus.PENDING).count(),
        "in_preparation": Client.objects.filter(active=True, tax_status=DeclarationStatus.IN_PREPARATION).count(),
        "ready_for_review": Client.objects.filter(active=True, tax_status=DeclarationStatus.READY_FOR_REVIEW).count(),
        "transmitted": Client.objects.filter(active=True, tax_status=DeclarationStatus.TRANSMITTED).count(),
    }
    return render(request, "core/home.html", context)

# Create your views here.
