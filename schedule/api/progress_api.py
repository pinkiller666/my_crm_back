from django.utils.timezone import now
from artworks.models import Commission, Artist


def get_month_progress():
    today = now().date()
    current_month = today.strftime("%Y-%m")

    commissions = Commission.objects.filter(
        accepted_at__year=today.year,
        accepted_at__month=today.month
    )

    total_orders = commissions.count()
    total_amount = sum(c.amount for c in commissions)

    return {
        "month": current_month,
        "total_orders": total_orders,
        "total_amount": total_amount,
    }


def get_month_progress_full():
    today = now().date()

    commissions = Commission.objects.filter(
        accepted_at__year=today.year,
        accepted_at__month=today.month
    ).select_related('artist')

    commissions_data = [
        {
            "id": c.id,
            "artist": {
                "id": c.artist.id,
                "name": c.artist.name,
            },
            "amount": float(c.amount),
            "comment": c.comment,
            "accepted_at": str(c.accepted_at)
        }
        for c in commissions
    ]

    return {
        "month": today.strftime("%Y-%m"),
        "commissions": commissions_data
    }

def get_artist_for_progres():
    return Artist.objects.values('id', 'name')
