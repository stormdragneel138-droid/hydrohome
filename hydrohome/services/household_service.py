"""Household use-cases: validate, then persist."""
from hydrohome.errors import ValidationError
from hydrohome.services.validators import validate_household


class HouseholdService:
    def __init__(self, repo):
        self.repo = repo

    def add(self, form):
        return self.repo.add(validate_household(form))

    def update(self, household_id, form):
        data = validate_household(form)
        if self.repo.update(household_id, data) == 0:
            raise ValidationError("That household no longer exists.")

    def delete(self, household_id):
        if self.repo.delete(household_id) == 0:
            raise ValidationError("That household no longer exists.")

    def get(self, household_id):
        return self.repo.get(household_id)

    def list(self, search=""):
        return self.repo.list_all(search)
