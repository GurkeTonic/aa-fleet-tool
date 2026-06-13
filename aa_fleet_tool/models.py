"""Data models for the Fleet Tool."""

# Django
from django.contrib.auth.models import User
from django.db import models

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter


class General(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("view_fleet_tool", "Can access Fleet Tool"),
            ("manage_doctrine", "Can manage fleet doctrines"),
        ]


class FleetCommander(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="fleet_commanders")
    character = models.OneToOneField(
        EveCharacter, on_delete=models.CASCADE, related_name="fleet_commander"
    )
    # Only active FCs are polled. The FC turns this on via "Fleet Start"; it is
    # turned off again on "Fleet Stop" or automatically when the fleet ends.
    is_active = models.BooleanField(default=False)
    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["character__character_name"]

    def __str__(self):
        return self.character.character_name

    def start(self):
        from django.utils import timezone
        self.is_active = True
        self.activated_at = timezone.now()
        self.save(update_fields=["is_active", "activated_at"])

    def stop(self):
        self.is_active = False
        self.activated_at = None
        self.save(update_fields=["is_active", "activated_at"])


class ActiveFleet(models.Model):
    fc = models.OneToOneField(FleetCommander, on_delete=models.CASCADE, related_name="active_fleet")
    fleet_id = models.BigIntegerField()
    name = models.CharField(max_length=100, blank=True, default="")
    motd = models.TextField(blank=True, default="")
    is_free_move = models.BooleanField(default=False)
    is_registered = models.BooleanField(default=False)
    is_voice_enabled = models.BooleanField(default=False)
    last_updated = models.DateTimeField(null=True, blank=True)
    # Links created via the FAT/SRP buttons, kept so the Fleet Ping can include them.
    fat_link_hash = models.CharField(max_length=64, blank=True, default="")
    srp_link_code = models.CharField(max_length=64, blank=True, default="")

    def __str__(self):
        return f"Fleet {self.fleet_id} ({self.fc})"

    @property
    def member_count(self):
        return self.members.count()


class FleetSnapshot(models.Model):
    """Composition counts captured at each member sync — feeds the live graph.

    Tied to the ActiveFleet (CASCADE), so snapshots are removed automatically
    when the fleet ends.
    """

    fleet = models.ForeignKey(ActiveFleet, on_delete=models.CASCADE, related_name="snapshots")
    timestamp = models.DateTimeField()
    total = models.PositiveIntegerField(default=0)
    dps = models.PositiveIntegerField(default=0)
    logi = models.PositiveIntegerField(default=0)
    booster = models.PositiveIntegerField(default=0)
    ewar = models.PositiveIntegerField(default=0)
    other = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"Snapshot {self.fleet_id} @ {self.timestamp:%H:%M:%S}"


class FleetWing(models.Model):
    fleet = models.ForeignKey(ActiveFleet, on_delete=models.CASCADE, related_name="wings")
    wing_id = models.BigIntegerField()
    name = models.CharField(max_length=100, default="")

    class Meta:
        unique_together = ("fleet", "wing_id")
        ordering = ["wing_id"]

    def __str__(self):
        return self.name or f"Wing {self.wing_id}"


class FleetSquad(models.Model):
    wing = models.ForeignKey(FleetWing, on_delete=models.CASCADE, related_name="squads")
    squad_id = models.BigIntegerField()
    name = models.CharField(max_length=100, default="")

    class Meta:
        unique_together = ("wing", "squad_id")
        ordering = ["squad_id"]

    def __str__(self):
        return self.name or f"Squad {self.squad_id}"


ROLE_CHOICES = [
    ("fleet_commander", "FC"),
    ("wing_commander", "WC"),
    ("squad_commander", "SC"),
    ("squad_member", "Member"),
]

ROLE_BADGE = {
    "fleet_commander": "danger",
    "wing_commander": "warning",
    "squad_commander": "info",
    "squad_member": "secondary",
}


class FleetMember(models.Model):
    fleet = models.ForeignKey(ActiveFleet, on_delete=models.CASCADE, related_name="members")
    character_id = models.IntegerField()
    character_name = models.CharField(max_length=100, default="")
    ship_type_id = models.IntegerField(default=0)
    ship_name = models.CharField(max_length=100, default="")
    solar_system_id = models.IntegerField(default=0)
    system_name = models.CharField(max_length=100, default="")
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default="squad_member")
    role_name = models.CharField(max_length=100, default="")
    wing_id = models.BigIntegerField(null=True, blank=True)
    squad_id = models.BigIntegerField(null=True, blank=True)
    join_time = models.DateTimeField(null=True, blank=True)
    takes_fleet_warp = models.BooleanField(default=True)
    station_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("fleet", "character_id")
        ordering = ["role", "character_name"]

    def __str__(self):
        return self.character_name

    @property
    def role_short(self):
        return dict(ROLE_CHOICES).get(self.role, self.role)

    @property
    def role_badge_color(self):
        return ROLE_BADGE.get(self.role, "secondary")


class Doctrine(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="doctrines"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class DoctrineShip(models.Model):
    ROLE_HINT_CHOICES = [
        ("any", "Any"),
        ("dps", "DPS"),
        ("logi", "Logi"),
        ("booster", "Booster"),
        ("fc", "FC"),
        ("ewar", "EWAR"),
        ("hauler", "Hauler"),
        ("scout", "Scout"),
    ]

    doctrine = models.ForeignKey(Doctrine, on_delete=models.CASCADE, related_name="ships")
    ship_type_id = models.IntegerField()
    ship_name = models.CharField(max_length=100)
    role_hint = models.CharField(max_length=20, choices=ROLE_HINT_CHOICES, default="any")

    class Meta:
        unique_together = ("doctrine", "ship_type_id")
        ordering = ["role_hint", "ship_name"]

    def __str__(self):
        return f"{self.ship_name} ({self.get_role_hint_display()})"


class MOTDTemplate(models.Model):
    name = models.CharField(max_length=100)
    text = models.TextField()
    # Public templates form the shared library (managed via manage_doctrine).
    # Private templates (is_public=False) belong to and are only visible to their
    # creator.
    is_public = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="motd_templates"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class FleetLayout(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="fleet_layouts"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class FleetLayoutWing(models.Model):
    layout = models.ForeignKey(FleetLayout, on_delete=models.CASCADE, related_name="wings")
    position = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ("layout", "position")
        ordering = ["position"]

    def __str__(self):
        return f"{self.layout.name} / {self.name}"


class FleetLayoutSquad(models.Model):
    wing = models.ForeignKey(FleetLayoutWing, on_delete=models.CASCADE, related_name="squads")
    position = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ("wing", "position")
        ordering = ["position"]

    def __str__(self):
        return self.name


class FleetToolConfiguration(models.Model):
    enable_fat_link = models.BooleanField(
        default=False,
        help_text="Show 'Create FAT Link' button in fleet detail (requires afat).",
    )
    enable_srp_link = models.BooleanField(
        default=False,
        help_text="Show 'Create SRP Link' button in fleet detail (requires aasrp).",
    )
    use_fittings_doctrines = models.BooleanField(
        default=False,
        help_text="Include doctrines from the fittings module in the doctrine dropdown (requires fittings).",
    )

    class Meta:
        verbose_name = "Fleet Tool Configuration"
        verbose_name_plural = "Fleet Tool Configuration"

    def __str__(self):
        return "Fleet Tool Configuration"

    @classmethod
    def get_config(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Webhook(models.Model):
    """A reusable Discord webhook a FleetType can post Fleet Pings to."""

    name = models.CharField(max_length=100)
    url = models.URLField(max_length=500, help_text="Discord webhook URL.")
    is_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class FleetType(models.Model):
    """A fleet type the FC selects — also the Discord ping target.

    The ``name`` is reused for the afat/aasrp categorisation when FAT/SRP links
    are created; the linked ``webhooks`` + ``mention`` drive the Fleet Ping.
    """

    MENTION_CHOICES = [
        ("", "None"),
        ("here", "@here"),
        ("everyone", "@everyone"),
    ]

    name = models.CharField(max_length=100, unique=True)
    webhooks = models.ManyToManyField(
        Webhook, blank=True, related_name="fleet_types",
        help_text="Discord webhooks the Fleet Ping posts to for this fleet type.",
    )
    mention = models.CharField(
        max_length=10, choices=MENTION_CHOICES, blank=True, default="",
        help_text="What to mention in the ping. None = no mention.",
    )
    is_enabled = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Staging(models.Model):
    """A staging location (system) the FC can attach to a Fleet Ping."""

    name = models.CharField(max_length=100)
    system = models.CharField(max_length=100, help_text="Solar system name, e.g. Jita.")
    is_enabled = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.name} ({self.system})"
