import json
from unittest import mock
from unittest.case import TestCase

import pytest
from core.constants import INTEGER, STRING
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from environments.identities.models import Identity
from environments.identities.traits.constants import (
    TRAIT_STRING_VALUE_MAX_LENGTH,
)
from environments.identities.traits.models import Trait
from environments.models import Environment, EnvironmentAPIKey
from organisations.models import Organisation, OrganisationRole
from projects.models import Project
from util.tests import Helper


class SDKTraitsTest(APITestCase):
    JSON = "application/json"

    def setUp(self) -> None:
        self.organisation = Organisation.objects.create(name="Test organisation")
        project = Project.objects.create(
            name="Test project", organisation=self.organisation, enable_dynamo_db=True
        )
        self.environment = Environment.objects.create(
            name="Test environment", project=project
        )
        self.identity = Identity.objects.create(
            identifier="test-user", environment=self.environment
        )
        self.client.credentials(HTTP_X_ENVIRONMENT_KEY=self.environment.api_key)
        self.trait_key = "trait_key"
        self.trait_value = "trait_value"

    def test_can_set_trait_for_an_identity(self):
        # Given
        url = reverse("api-v1:sdk-traits-list")

        # When
        res = self.client.post(
            url, data=self._generate_json_trait_data(), content_type=self.JSON
        )

        # Then
        assert res.status_code == status.HTTP_200_OK

        # and
        assert Trait.objects.filter(
            identity=self.identity, trait_key=self.trait_key
        ).exists()

    def test_cannot_set_trait_for_an_identity_for_organisations_without_persistence(
        self,
    ):
        # Given
        url = reverse("api-v1:sdk-traits-list")

        # an organisation that is configured to not store traits
        self.organisation.persist_trait_data = False
        self.organisation.save()

        # When
        response = self.client.post(
            url, data=self._generate_json_trait_data(), content_type=self.JSON
        )

        # Then
        # the request fails
        assert response.status_code == status.HTTP_403_FORBIDDEN
        response_json = response.json()
        assert response_json["detail"] == (
            "Organisation is not authorised to store traits."
        )

        # and no traits are stored
        assert Trait.objects.count() == 0

    def test_can_set_trait_with_boolean_value_for_an_identity(self):
        # Given
        url = reverse("api-v1:sdk-traits-list")
        trait_value = True

        # When
        res = self.client.post(
            url,
            data=self._generate_json_trait_data(trait_value=trait_value),
            content_type=self.JSON,
        )

        # Then
        assert res.status_code == status.HTTP_200_OK

        # and
        assert (
            Trait.objects.get(
                identity=self.identity, trait_key=self.trait_key
            ).get_trait_value()
            == trait_value
        )

    def test_can_set_trait_with_identity_value_for_an_identity(self):
        # Given
        url = reverse("api-v1:sdk-traits-list")
        trait_value = 12

        # When
        res = self.client.post(
            url,
            data=self._generate_json_trait_data(trait_value=trait_value),
            content_type=self.JSON,
        )

        # Then
        assert res.status_code == status.HTTP_200_OK

        # and
        assert (
            Trait.objects.get(
                identity=self.identity, trait_key=self.trait_key
            ).get_trait_value()
            == trait_value
        )

    def test_can_set_trait_with_float_value_for_an_identity(self):
        # Given
        url = reverse("api-v1:sdk-traits-list")
        float_trait_value = 10.5

        # When
        res = self.client.post(
            url,
            data=self._generate_json_trait_data(trait_value=float_trait_value),
            content_type=self.JSON,
        )

        # Then
        assert res.status_code == status.HTTP_200_OK

        # and
        assert (
            Trait.objects.get(
                identity=self.identity, trait_key=self.trait_key
            ).get_trait_value()
            == float_trait_value
        )

    def test_add_trait_creates_identity_if_it_doesnt_exist(self):
        # Given
        url = reverse("api-v1:sdk-traits-list")
        identifier = "new-identity"

        # When
        res = self.client.post(
            url,
            data=self._generate_json_trait_data(identifier=identifier),
            content_type=self.JSON,
        )

        # Then
        assert res.status_code == status.HTTP_200_OK

        # and
        assert Identity.objects.filter(
            identifier=identifier, environment=self.environment
        ).exists()

        # and
        assert Trait.objects.filter(
            identity__identifier=identifier, trait_key=self.trait_key
        ).exists()

    def test_trait_is_updated_if_already_exists(self):
        # Given
        url = reverse("api-v1:sdk-traits-list")
        trait = Trait.objects.create(
            trait_key=self.trait_key,
            value_type=STRING,
            string_value=self.trait_value,
            identity=self.identity,
        )
        new_value = "Some new value"

        # When
        self.client.post(
            url,
            data=self._generate_json_trait_data(trait_value=new_value),
            content_type=self.JSON,
        )

        # Then
        trait.refresh_from_db()
        assert trait.get_trait_value() == new_value

    def test_increment_value_increments_trait_value_if_value_positive_integer(self):
        # Given
        initial_value = 2
        increment_by = 2

        url = reverse("api-v1:sdk-traits-increment-value")
        trait = Trait.objects.create(
            identity=self.identity,
            trait_key=self.trait_key,
            value_type=INTEGER,
            integer_value=initial_value,
        )
        data = {
            "trait_key": self.trait_key,
            "identifier": self.identity.identifier,
            "increment_by": increment_by,
        }

        # When
        self.client.post(url, data=data)

        # Then
        trait.refresh_from_db()
        assert trait.get_trait_value() == initial_value + increment_by

    def test_increment_value_decrements_trait_value_if_value_negative_integer(self):
        # Given
        initial_value = 2
        increment_by = -2

        url = reverse("api-v1:sdk-traits-increment-value")
        trait = Trait.objects.create(
            identity=self.identity,
            trait_key=self.trait_key,
            value_type=INTEGER,
            integer_value=initial_value,
        )
        data = {
            "trait_key": self.trait_key,
            "identifier": self.identity.identifier,
            "increment_by": increment_by,
        }

        # When
        self.client.post(url, data=data)

        # Then
        trait.refresh_from_db()
        assert trait.get_trait_value() == initial_value + increment_by

    def test_increment_value_initialises_trait_with_a_value_of_zero_if_it_doesnt_exist(
        self,
    ):
        # Given
        increment_by = 1

        url = reverse("api-v1:sdk-traits-increment-value")
        data = {
            "trait_key": self.trait_key,
            "identifier": self.identity.identifier,
            "increment_by": increment_by,
        }

        # When
        self.client.post(url, data=data)

        # Then
        trait = Trait.objects.get(trait_key=self.trait_key, identity=self.identity)
        assert trait.get_trait_value() == increment_by

    def test_increment_value_returns_400_if_trait_value_not_integer(self):
        # Given
        url = reverse("api-v1:sdk-traits-increment-value")
        Trait.objects.create(
            identity=self.identity,
            trait_key=self.trait_key,
            value_type=STRING,
            string_value="str",
        )
        data = {
            "trait_key": self.trait_key,
            "identifier": self.identity.identifier,
            "increment_by": 2,
        }

        # When
        res = self.client.post(url, data=data)

        # Then
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_set_trait_with_too_long_string_value_returns_400(self):
        # Given
        url = reverse("api-v1:sdk-traits-list")
        trait_value = "t" * (TRAIT_STRING_VALUE_MAX_LENGTH + 1)

        # When
        res = self.client.post(
            url,
            data=self._generate_json_trait_data(trait_value=trait_value),
            content_type=self.JSON,
        )

        # Then
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            f"Value string is too long. Must be less than {TRAIT_STRING_VALUE_MAX_LENGTH} character"
            == res.json()["trait_value"][0]
        )

    def test_can_set_trait_with_bad_value_for_an_identity(self):
        # Given
        url = reverse("api-v1:sdk-traits-list")
        bad_trait_value = {"foo": "bar"}

        # When
        res = self.client.post(
            url,
            data=self._generate_json_trait_data(trait_value=bad_trait_value),
            content_type=self.JSON,
        )

        # Then
        assert res.status_code == status.HTTP_200_OK

        # and
        assert Trait.objects.get(
            identity=self.identity, trait_key=self.trait_key
        ).get_trait_value() == str(bad_trait_value)

    def test_bulk_create_traits(self):
        # Given
        num_traits = 20
        url = reverse("api-v1:sdk-traits-bulk-create")
        traits = [
            self._generate_trait_data(trait_key=f"trait_{i}", identifier="user_{i}")
            for i in range(num_traits)
        ]
        identifiers = [trait["identity"]["identifier"] for trait in traits]

        # When
        response = self.client.put(
            url, data=json.dumps(traits), content_type="application/json"
        )

        # Then
        assert response.status_code == status.HTTP_200_OK
        assert (
            Trait.objects.filter(identity__identifier__in=identifiers).count()
            == num_traits
        )

    def test_bulk_create_traits_when_bad_trait_value_sent_then_trait_value_stringified(
        self,
    ):
        # Given
        num_traits = 5
        url = reverse("api-v1:sdk-traits-bulk-create")
        traits = [
            self._generate_trait_data(trait_key=f"trait_{i}") for i in range(num_traits)
        ]

        # add some bad data to test
        bad_trait_key = "trait_999"
        bad_trait_value = {"foo": "bar"}
        traits.append(
            {
                "trait_value": bad_trait_value,
                "trait_key": bad_trait_key,
                "identity": {"identifier": self.identity.identifier},
            }
        )

        # When
        response = self.client.put(
            url, data=json.dumps(traits), content_type="application/json"
        )

        # Then
        assert response.status_code == status.HTTP_200_OK
        assert Trait.objects.filter(identity=self.identity).count() == num_traits + 1

        # and
        assert Trait.objects.get(
            identity=self.identity, trait_key=bad_trait_key
        ).get_trait_value() == str(bad_trait_value)

    def test_sending_null_value_in_bulk_create_deletes_trait_for_identity(self):
        # Given
        url = reverse("api-v1:sdk-traits-bulk-create")
        trait_to_delete = Trait.objects.create(
            trait_key=self.trait_key,
            value_type=STRING,
            string_value=self.trait_value,
            identity=self.identity,
        )
        trait_key_to_keep = "another_trait_key"
        trait_to_keep = Trait.objects.create(
            trait_key=trait_key_to_keep,
            value_type=STRING,
            string_value="value is irrelevant",
            identity=self.identity,
        )
        data = [
            {
                "identity": {"identifier": self.identity.identifier},
                "trait_key": self.trait_key,
                "trait_value": None,
            }
        ]

        # When
        response = self.client.put(
            url, data=json.dumps(data), content_type="application/json"
        )

        # Then
        # the request is successful
        assert response.status_code == status.HTTP_200_OK

        # and the trait is deleted
        assert not Trait.objects.filter(id=trait_to_delete.id).exists()

        # but the trait missing from the request is left untouched
        assert Trait.objects.filter(id=trait_to_keep.id).exists()

    def test_bulk_create_traits_when_float_value_sent_then_trait_value_correct(self):
        # Given
        url = reverse("api-v1:sdk-traits-bulk-create")
        traits = []

        # add float value trait
        float_trait_key = "float_key_999"
        float_trait_value = 45.88
        traits.append(
            {
                "trait_value": float_trait_value,
                "trait_key": float_trait_key,
                "identity": {"identifier": self.identity.identifier},
            }
        )

        # When
        response = self.client.put(
            url, data=json.dumps(traits), content_type="application/json"
        )

        # Then
        assert response.status_code == status.HTTP_200_OK
        assert Trait.objects.filter(identity=self.identity).count() == 1

        # and
        assert (
            Trait.objects.get(
                identity=self.identity, trait_key=float_trait_key
            ).get_trait_value()
            == float_trait_value
        )

    @override_settings(EDGE_API_URL="http://localhost")
    @mock.patch("environments.identities.traits.views.forward_trait_request")
    def test_post_trait_calls_forward_trait_request_with_correct_arguments(
        self, mocked_forward_trait_request
    ):
        # Given
        url = reverse("api-v1:sdk-traits-list")
        data = self._generate_json_trait_data()

        # When
        self.client.post(url, data=data, content_type=self.JSON)

        # Then
        args, kwargs = mocked_forward_trait_request.delay.call_args_list[0]
        assert args == ()
        assert kwargs["args"][0] == "POST"
        assert kwargs["args"][1].get("X-Environment-Key") == self.environment.api_key
        assert kwargs["args"][2] == self.environment.project.id
        assert kwargs["args"][3] == json.loads(data)

    @override_settings(EDGE_API_URL="http://localhost")
    @mock.patch("environments.identities.traits.views.forward_trait_request")
    def test_increment_value_calls_forward_trait_request_with_correct_arguments(
        self, mocked_forward_trait_request
    ):
        # Given
        url = reverse("api-v1:sdk-traits-increment-value")
        data = {
            "trait_key": self.trait_key,
            "identifier": self.identity.identifier,
            "increment_by": 1,
        }

        # When
        self.client.post(url, data=data)

        # Then
        args, kwargs = mocked_forward_trait_request.delay.call_args_list[0]
        assert args == ()
        assert kwargs["args"][0] == "POST"
        assert kwargs["args"][1].get("X-Environment-Key") == self.environment.api_key
        assert kwargs["args"][2] == self.environment.project.id

        # and the structure of payload was correct
        assert kwargs["args"][3]["identity"]["identifier"] == data["identifier"]
        assert kwargs["args"][3]["trait_key"] == data["trait_key"]
        assert kwargs["args"][3]["trait_value"]

    @override_settings(EDGE_API_URL="http://localhost")
    @mock.patch("environments.identities.traits.views.forward_trait_requests")
    def test_bulk_create_traits_calls_forward_trait_request_with_correct_arguments(
        self, mocked_forward_trait_requests
    ):
        # Given
        url = reverse("api-v1:sdk-traits-bulk-create")
        request_data = [
            {
                "identity": {"identifier": "test_user_123"},
                "trait_key": "key",
                "trait_value": "value",
            },
            {
                "identity": {"identifier": "test_user_123"},
                "trait_key": "key1",
                "trait_value": "value1",
            },
        ]

        # When
        self.client.put(
            url, data=json.dumps(request_data), content_type="application/json"
        )

        # Then

        # Then
        args, kwargs = mocked_forward_trait_requests.delay.call_args_list[0]
        assert args == ()
        assert kwargs["args"][0] == "PUT"
        assert kwargs["args"][1].get("X-Environment-Key") == self.environment.api_key
        assert kwargs["args"][2] == self.environment.project.id
        assert kwargs["args"][3] == request_data

    def test_create_trait_returns_403_if_client_cannot_set_traits(self):
        # Given
        url = reverse("api-v1:sdk-traits-list")
        data = {
            "identity": {"identifier": self.identity.identifier},
            "trait_key": "foo",
            "trait_value": "bar",
        }

        self.environment.allow_client_traits = False
        self.environment.save()

        # When
        response = self.client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

        # Then
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_server_key_can_create_trait_if_not_allow_client_traits(self):
        # Given
        url = reverse("api-v1:sdk-traits-list")
        data = {
            "identity": {"identifier": self.identity.identifier},
            "trait_key": "foo",
            "trait_value": "bar",
        }

        server_api_key = EnvironmentAPIKey.objects.create(environment=self.environment)
        self.client.credentials(HTTP_X_ENVIRONMENT_KEY=server_api_key.key)

        self.environment.allow_client_traits = False
        self.environment.save()

        # When
        response = self.client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

        # Then
        assert response.status_code == status.HTTP_200_OK

    def test_bulk_create_traits_returns_403_if_client_cannot_set_traits(self):
        # Given
        url = reverse("api-v1:sdk-traits-bulk-create")
        data = [
            {
                "identity": {"identifier": self.identity.identifier},
                "trait_key": "foo",
                "trait_value": "bar",
            }
        ]

        self.environment.allow_client_traits = False
        self.environment.save()

        # When
        response = self.client.put(
            url, data=json.dumps(data), content_type="application/json"
        )

        # Then
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_server_key_can_bulk_create_traits_if_not_allow_client_traits(self):
        # Given
        url = reverse("api-v1:sdk-traits-bulk-create")
        data = [
            {
                "identity": {"identifier": self.identity.identifier},
                "trait_key": "foo",
                "trait_value": "bar",
            }
        ]

        server_api_key = EnvironmentAPIKey.objects.create(environment=self.environment)
        self.client.credentials(HTTP_X_ENVIRONMENT_KEY=server_api_key.key)

        self.environment.allow_client_traits = False
        self.environment.save()

        # When
        response = self.client.put(
            url, data=json.dumps(data), content_type="application/json"
        )

        # Then
        assert response.status_code == status.HTTP_200_OK

    def _generate_trait_data(self, identifier=None, trait_key=None, trait_value=None):
        identifier = identifier or self.identity.identifier
        trait_key = trait_key or self.trait_key
        trait_value = trait_value or self.trait_value

        return {
            "identity": {"identifier": identifier},
            "trait_key": trait_key,
            "trait_value": trait_value,
        }

    def _generate_json_trait_data(
        self, identifier=None, trait_key=None, trait_value=None
    ):
        return json.dumps(self._generate_trait_data(identifier, trait_key, trait_value))


@pytest.mark.django_db
class TraitViewSetTestCase(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        user = Helper.create_ffadminuser()
        self.client.force_authenticate(user=user)

        organisation = Organisation.objects.create(name="Test org")
        user.add_organisation(organisation, OrganisationRole.ADMIN)

        self.project = Project.objects.create(
            name="Test project", organisation=organisation
        )
        self.environment = Environment.objects.create(
            name="Test environment", project=self.project
        )
        self.identity = Identity.objects.create(
            identifier="test-user", environment=self.environment
        )

    def test_delete_trait_only_deletes_single_trait_if_query_param_not_provided(self):
        # Given
        trait_key = "trait_key"
        trait_value = "trait_value"
        identity_2 = Identity.objects.create(
            identifier="test-user-2", environment=self.environment
        )

        trait = Trait.objects.create(
            identity=self.identity,
            trait_key=trait_key,
            value_type=STRING,
            string_value=trait_value,
        )
        trait_2 = Trait.objects.create(
            identity=identity_2,
            trait_key=trait_key,
            value_type=STRING,
            string_value=trait_value,
        )

        url = reverse(
            "api-v1:environments:identities-traits-detail",
            args=[self.environment.api_key, self.identity.id, trait.id],
        )

        # When
        self.client.delete(url)

        # Then
        assert not Trait.objects.filter(pk=trait.id).exists()

        # and
        assert Trait.objects.filter(pk=trait_2.id).exists()

    def test_delete_trait_deletes_all_traits_if_query_param_provided(self):
        # Given
        trait_key = "trait_key"
        trait_value = "trait_value"
        identity_2 = Identity.objects.create(
            identifier="test-user-2", environment=self.environment
        )

        trait = Trait.objects.create(
            identity=self.identity,
            trait_key=trait_key,
            value_type=STRING,
            string_value=trait_value,
        )
        trait_2 = Trait.objects.create(
            identity=identity_2,
            trait_key=trait_key,
            value_type=STRING,
            string_value=trait_value,
        )

        base_url = reverse(
            "api-v1:environments:identities-traits-detail",
            args=[self.environment.api_key, self.identity.id, trait.id],
        )
        url = base_url + "?deleteAllMatchingTraits=true"

        # When
        self.client.delete(url)

        # Then
        assert not Trait.objects.filter(pk=trait.id).exists()

        # and
        assert not Trait.objects.filter(pk=trait_2.id).exists()

    def test_delete_trait_only_deletes_traits_in_current_environment(self):
        # Given
        environment_2 = Environment.objects.create(
            name="Test environment", project=self.project
        )
        trait_key = "trait_key"
        trait_value = "trait_value"
        identity_2 = Identity.objects.create(
            identifier="test-user-2", environment=environment_2
        )

        trait = Trait.objects.create(
            identity=self.identity,
            trait_key=trait_key,
            value_type=STRING,
            string_value=trait_value,
        )
        trait_2 = Trait.objects.create(
            identity=identity_2,
            trait_key=trait_key,
            value_type=STRING,
            string_value=trait_value,
        )

        base_url = reverse(
            "api-v1:environments:identities-traits-detail",
            args=[self.environment.api_key, self.identity.id, trait.id],
        )
        url = base_url + "?deleteAllMatchingTraits=true"

        # When
        self.client.delete(url)

        # Then
        assert not Trait.objects.filter(pk=trait.id).exists()

        # and
        assert Trait.objects.filter(pk=trait_2.id).exists()


def test_set_trait_for_an_identity_is_not_throttled_by_user_throttle(
    settings, identity, environment, api_client
):
    # Given
    settings.REST_FRAMEWORK = {"DEFAULT_THROTTLE_RATES": {"user": "1/minute"}}

    api_client.credentials(HTTP_X_ENVIRONMENT_KEY=environment.api_key)

    url = reverse("api-v1:sdk-traits-list")
    data = {
        "identity": {"identifier": identity.identifier},
        "trait_key": "key",
        "trait_value": "value",
    }

    # When
    for _ in range(10):
        res = api_client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

        # Then
        assert res.status_code == status.HTTP_200_OK
