# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` models module.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import ddt
import mock
from faker import Factory as FakerFactory
from pytest import mark, raises

from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.storage import Storage

from enterprise.models import (EnrollmentNotificationEmailTemplate, EnterpriseCourseEnrollment, EnterpriseCustomer,
                               EnterpriseCustomerBrandingConfiguration, EnterpriseCustomerEntitlement,
                               EnterpriseCustomerUser, PendingEnterpriseCustomerUser, UserDataSharingConsentAudit,
                               logo_path)
from integrated_channels.integrated_channel.models import (EnterpriseCustomerPluginConfiguration,
                                                           EnterpriseIntegratedChannel)
from integrated_channels.sap_success_factors.models import (CatalogTransmissionAudit, LearnerDataTransmissionAudit,
                                                            SAPSuccessFactorsEnterpriseCustomerConfiguration,
                                                            SAPSuccessFactorsGlobalConfiguration)
from test_utils.factories import (EnterpriseCustomerEntitlementFactory, EnterpriseCustomerFactory,
                                  EnterpriseCustomerIdentityProviderFactory, EnterpriseCustomerUserFactory,
                                  PendingEnrollmentFactory, PendingEnterpriseCustomerUserFactory,
                                  UserDataSharingConsentAuditFactory, UserFactory)


@mark.django_db
@ddt.ddt
class TestPendingEnrollment(unittest.TestCase):
    """
    Test for pending enrollment
    """
    def setUp(self):
        email = 'bob@jones.com'
        course_id = 'course-v1:edX+DemoX+DemoCourse'
        pending_link = PendingEnterpriseCustomerUserFactory(user_email=email)
        self.enrollment = PendingEnrollmentFactory(user=pending_link, course_id=course_id)
        self.user = UserFactory(email=email)
        super(TestPendingEnrollment, self).setUp()

    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test conversion to string.
        """
        expected_str = '<PendingEnrollment for email bob@jones.com in course with ID course-v1:edX+DemoX+DemoCourse>'
        assert expected_str == method(self.enrollment)

    @mock.patch('enterprise.lms_api.CourseKey')
    @mock.patch('enterprise.lms_api.CourseEnrollment')
    def test_complete_enrollment(self, mock_course_enrollment, mock_course_key):
        mock_course_key.from_string.return_value = None
        mock_course_enrollment.enroll.return_value = None
        self.enrollment.complete_enrollment()  # pylint: disable=no-member
        mock_course_enrollment.enroll.assert_called_once_with(self.user, None, mode='audit', check_access=True)
        mock_course_key.from_string.assert_called_once_with(self.enrollment.course_id)


@mark.django_db
@ddt.ddt
class TestEnterpriseCourseEnrollment(unittest.TestCase):
    """
    Test for EnterpriseCourseEnrollment
    """
    def setUp(self):
        self.username = 'DarthVader'
        self.user = UserFactory(username=self.username)
        self.course_id = 'course-v1:edX+DemoX+DemoCourse'
        self.enterprise_customer_user = EnterpriseCustomerUserFactory(user_id=self.user.id)
        self.enrollment = EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )
        super(TestEnterpriseCourseEnrollment, self).setUp()

    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test conversion to string.
        """
        expected_str = (
            '<EnterpriseCourseEnrollment for user DarthVader in '
            'course with ID course-v1:edX+DemoX+DemoCourse>'
        )
        assert expected_str == method(self.enrollment)

    def test_consent_available_consent_stored(self):
        self.enrollment.consent_granted = True
        assert self.enrollment.consent_available() is True

    def test_consent_denied_consent_stored(self):
        self.enrollment.consent_granted = False
        assert self.enrollment.consent_available() is False

    def test_consent_not_stored_audit_available(self):
        UserDataSharingConsentAuditFactory(
            user=self.enterprise_customer_user,
            state='enabled',
        )
        assert self.enrollment.consent_available() is True

    def test_consent_not_stored_audit_available_denied(self):
        UserDataSharingConsentAuditFactory(
            user=self.enterprise_customer_user,
            state='disabled',
        )
        assert self.enrollment.consent_available() is False

    def test_consent_not_stored_no_audit_available(self):
        assert self.enrollment.consent_available() is False


@mark.django_db
class TestEnterpriseCustomerManager(unittest.TestCase):
    """
    Tests for enterprise customer manager.
    """

    def tearDown(self):
        super(TestEnterpriseCustomerManager, self).tearDown()
        # A bug in pylint-django: https://github.com/landscapeio/pylint-django/issues/53
        # Reports violation on this line: "Instance of 'Manager' has no 'all' member"
        EnterpriseCustomer.objects.all().delete()  # pylint: disable=no-member

    def test_active_customers_get_queryset_returns_only_active(self):
        """
        Test that get_queryset on custom model manager returns only active customers.
        """
        customer1 = EnterpriseCustomerFactory(active=True)
        customer2 = EnterpriseCustomerFactory(active=True)
        inactive_customer = EnterpriseCustomerFactory(active=False)

        active_customers = EnterpriseCustomer.active_customers.all()
        self.assertTrue(all(customer.active for customer in active_customers))
        self.assertIn(customer1, active_customers)
        self.assertIn(customer2, active_customers)
        self.assertNotIn(inactive_customer, active_customers)


@mark.django_db
@ddt.ddt
class TestUserDataSharingConsentAudit(unittest.TestCase):
    """
    Tests of the UserDataSharingConsent model.
    """
    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test ``UserDataSharingConsentAudit`` conversion to string
        """
        user = UserFactory(email='bob@jones.com')
        enterprise_customer = EnterpriseCustomerFactory(name='EvilCorp')
        ec_user = EnterpriseCustomerUserFactory(user_id=user.id, enterprise_customer=enterprise_customer)
        audit = UserDataSharingConsentAuditFactory(user=ec_user)
        expected_to_str = "<UserDataSharingConsentAudit for bob@jones.com and EvilCorp: not_set>"
        assert expected_to_str == method(audit)


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomer(unittest.TestCase):
    """
    Tests of the EnterpriseCustomer model.
    """

    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test ``EnterpriseCustomer`` conversion to string.
        """
        faker = FakerFactory.create()
        customer_uuid = faker.uuid4()
        customer = EnterpriseCustomerFactory(uuid=customer_uuid, name="QWERTY")
        expected_to_str = "<{class_name} {customer_uuid}: {name}>".format(
            class_name=EnterpriseCustomer.__name__,
            customer_uuid=customer_uuid,
            name=customer.name
        )
        self.assertEqual(method(customer), expected_to_str)

    def test_identity_provider(self):
        """
        Test identity_provider property returns correct value without errors.
        """
        faker = FakerFactory.create()
        provider_id = faker.slug()
        customer = EnterpriseCustomerFactory()
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=customer)

        assert customer.identity_provider == provider_id  # pylint: disable=no-member

    def test_no_identity_provider(self):
        """
        Test identity_provider property returns correct value without errors.

        Test that identity_provider property does not raise ObjectDoesNotExist and returns None
        if enterprise customer doesn not have an associated identity provider.
        """
        customer = EnterpriseCustomerFactory()
        assert customer.identity_provider is None  # pylint: disable=no-member


@mark.django_db
@ddt.ddt
# TODO: remove suppression when https://github.com/landscapeio/pylint-django/issues/78 is fixed
# pylint: disable=no-member
class TestEnterpriseCustomerUserManager(unittest.TestCase):
    """
    Tests EnterpriseCustomerUserManager.
    """

    @ddt.data(
        "albert.einstein@princeton.edu", "richard.feynman@caltech.edu", "leo.susskind@stanford.edu"
    )
    def test_link_user_existing_user(self, user_email):
        enterprise_customer = EnterpriseCustomerFactory()
        user = UserFactory(email=user_email)
        assert len(EnterpriseCustomerUser.objects.all()) == 0, "Precondition check: no link records should exist"
        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=user_email)) == 0, \
            "Precondition check: no pending link records should exist"

        EnterpriseCustomerUser.objects.link_user(enterprise_customer, user_email)
        actual_records = EnterpriseCustomerUser.objects.filter(
            enterprise_customer=enterprise_customer, user_id=user.id  # pylint: disable=no-member
        )
        assert len(actual_records) == 1
        assert len(PendingEnterpriseCustomerUser.objects.all()) == 0, "No pending link records should have been created"

    @ddt.data(
        "yoda@jeditemple.net", "luke_skywalker@resistance.org", "darth_vader@empire.com"
    )
    def test_link_user_no_user(self, user_email):
        enterprise_customer = EnterpriseCustomerFactory()

        assert len(EnterpriseCustomerUser.objects.all()) == 0, "Precondition check: no link records should exist"
        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=user_email)) == 0, \
            "Precondition check: no pending link records should exist"

        EnterpriseCustomerUser.objects.link_user(enterprise_customer, user_email)
        actual_records = PendingEnterpriseCustomerUser.objects.filter(
            enterprise_customer=enterprise_customer, user_email=user_email
        )
        assert len(actual_records) == 1
        assert len(EnterpriseCustomerUser.objects.all()) == 0, "No pending link records should have been created"

    @ddt.data("email1@example.com", "email2@example.com")
    def test_get_link_by_email_linked_user(self, email):
        user = UserFactory(email=email)
        existing_link = EnterpriseCustomerUserFactory(user_id=user.id)
        assert EnterpriseCustomerUser.objects.get_link_by_email(email) == existing_link

    @ddt.data("email1@example.com", "email2@example.com")
    def test_get_link_by_email_pending_link(self, email):
        existing_pending_link = PendingEnterpriseCustomerUserFactory(user_email=email)
        assert EnterpriseCustomerUser.objects.get_link_by_email(email) == existing_pending_link

    @ddt.data("email1@example.com", "email2@example.com")
    def test_get_link_by_email_no_link(self, email):
        assert len(EnterpriseCustomerUser.objects.all()) == 0
        assert len(PendingEnterpriseCustomerUser.objects.all()) == 0
        assert EnterpriseCustomerUser.objects.get_link_by_email(email) is None

    @ddt.data("email1@example.com", "email2@example.com")
    def test_unlink_user_existing_user(self, email):
        other_email = "other_email@example.com"
        user1, user2 = UserFactory(email=email), UserFactory(email=other_email)
        enterprise_customer1, enterprise_customer2 = EnterpriseCustomerFactory(), EnterpriseCustomerFactory()
        EnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer1, user_id=user1.id)
        EnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer1, user_id=user2.id)
        EnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer2, user_id=user1.id)
        assert len(EnterpriseCustomerUser.objects.all()) == 3

        query_method = EnterpriseCustomerUser.objects.filter

        EnterpriseCustomerUser.objects.unlink_user(enterprise_customer1, email)
        # removes what was asked
        assert len(query_method(enterprise_customer=enterprise_customer1, user_id=user1.id)) == 0
        # keeps records of the same user with different EC (though it shouldn't be the case)
        assert len(query_method(enterprise_customer=enterprise_customer2, user_id=user1.id)) == 1
        # keeps records of other users
        assert len(query_method(user_id=user2.id)) == 1

    @ddt.data("email1@example.com", "email2@example.com")
    def test_unlink_user_pending_link(self, email):
        other_email = "other_email@example.com"
        enterprise_customer = EnterpriseCustomerFactory()
        PendingEnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer, user_email=email)
        PendingEnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer, user_email=other_email)
        assert len(PendingEnterpriseCustomerUser.objects.all()) == 2

        query_method = PendingEnterpriseCustomerUser.objects.filter

        EnterpriseCustomerUser.objects.unlink_user(enterprise_customer, email)
        # removes what was asked
        assert len(query_method(enterprise_customer=enterprise_customer, user_email=email)) == 0
        # keeps records of other users
        assert len(query_method(user_email=other_email)) == 1

    @ddt.data("email1@example.com", "email2@example.com")
    def test_unlink_user_existing_user_no_link(self, email):
        user = UserFactory(email=email)
        enterprise_customer = EnterpriseCustomerFactory()
        query_method = EnterpriseCustomerUser.objects.filter

        assert len(query_method(user_id=user.id)) == 0, "Precondition check: link record exists"

        with raises(EnterpriseCustomerUser.DoesNotExist):
            EnterpriseCustomerUser.objects.unlink_user(enterprise_customer, email)

    @ddt.data("email1@example.com", "email2@example.com")
    def test_unlink_user_no_user_no_pending_link(self, email):
        enterprise_customer = EnterpriseCustomerFactory()
        query_method = PendingEnterpriseCustomerUser.objects.filter

        assert len(query_method(user_email=email)) == 0, "Precondition check: link record exists"

        with raises(PendingEnterpriseCustomerUser.DoesNotExist):
            EnterpriseCustomerUser.objects.unlink_user(enterprise_customer, email)


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomerUser(unittest.TestCase):
    """
    Tests of the EnterpriseCustomerUser model.
    """

    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test ``EnterpriseCustomerUser`` conversion to string.
        """
        customer_user_id, user_id = 15, 12
        customer_user = EnterpriseCustomerUserFactory(id=customer_user_id, user_id=user_id)
        expected_to_str = "<EnterpriseCustomerUser {ID}>: {enterprise_name} - {user_id}".format(
            ID=customer_user_id,
            enterprise_name=customer_user.enterprise_customer.name,
            user_id=user_id
        )
        self.assertEqual(method(customer_user), expected_to_str)

    @ddt.data(
        "albert.einstein@princeton.edu", "richard.feynman@caltech.edu", "leo.susskind@stanford.edu"
    )
    def test_user_property_user_exists(self, email):
        user_instance = UserFactory(email=email)
        enterprise_customer_user = EnterpriseCustomerUserFactory(user_id=user_instance.id)  # pylint: disable=no-member
        assert enterprise_customer_user.user == user_instance  # pylint: disable=no-member

    @ddt.data(1, 42, 1138)
    def test_user_property_user_missing(self, user_id):
        enterprise_customer_user = EnterpriseCustomerUserFactory(user_id=user_id)
        assert enterprise_customer_user.user is None  # pylint: disable=no-member

    @ddt.data(
        "albert.einstein@princeton.edu", "richard.feynman@caltech.edu", "leo.susskind@stanford.edu"
    )
    # TODO: remove suppression when https://github.com/landscapeio/pylint-django/issues/78 is fixed
    # pylint: disable=no-member
    def test_user_email_property_user_exists(self, email):
        user = UserFactory(email=email)
        enterprise_customer_user = EnterpriseCustomerUserFactory(user_id=user.id)
        assert enterprise_customer_user.user_email == email

    # TODO: remove suppression when https://github.com/landscapeio/pylint-django/issues/78 is fixed
    # pylint: disable=no-member
    def test_user_email_property_user_missing(self):
        enterprise_customer_user = EnterpriseCustomerUserFactory(user_id=42)
        assert enterprise_customer_user.user_email is None

    @ddt.data(
        (True, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.ENABLED, [1, 2, 3], [1, 2, 3]),
        (True, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.DISABLED, [1, 2, 3], []),
        (True, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.NOT_SET, [1, 2, 3], []),
        (True, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.ENABLED, [1, 2, 3], [1, 2, 3]),
        (True, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.DISABLED, [1, 2, 3], []),
        (True, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.NOT_SET, [1, 2, 3], []),
        (True, EnterpriseCustomer.DATA_CONSENT_OPTIONAL, UserDataSharingConsentAudit.ENABLED, [1, 2, 3], [1, 2, 3]),
        (True, EnterpriseCustomer.DATA_CONSENT_OPTIONAL, UserDataSharingConsentAudit.DISABLED, [1, 2, 3], [1, 2, 3]),
        (True, EnterpriseCustomer.DATA_CONSENT_OPTIONAL, UserDataSharingConsentAudit.NOT_SET, [1, 2, 3], [1, 2, 3]),
        (False, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.ENABLED, [1, 2, 3], [1, 2, 3]),
        (False, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.DISABLED, [1, 2, 3], [1, 2, 3]),
        (False, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.NOT_SET, [1, 2, 3], [1, 2, 3]),
        (False, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.ENABLED, [1, 2, 3], [1, 2, 3]),
        (False, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.DISABLED, [1, 2, 3], [1, 2, 3]),
        (False, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.NOT_SET, [1, 2, 3], [1, 2, 3]),
        (False, EnterpriseCustomer.DATA_CONSENT_OPTIONAL, UserDataSharingConsentAudit.ENABLED, [1, 2, 3], [1, 2, 3]),
        (False, EnterpriseCustomer.DATA_CONSENT_OPTIONAL, UserDataSharingConsentAudit.DISABLED, [1, 2, 3], [1, 2, 3]),
        (False, EnterpriseCustomer.DATA_CONSENT_OPTIONAL, UserDataSharingConsentAudit.NOT_SET, [1, 2, 3], [1, 2, 3]),
        (True, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.ENABLED, [], []),
        (True, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.DISABLED, [], []),
        (True, EnterpriseCustomer.AT_LOGIN, UserDataSharingConsentAudit.NOT_SET, [], []),
        (True, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.ENABLED, [], []),
        (True, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.DISABLED, [], []),
        (True, EnterpriseCustomer.AT_ENROLLMENT, UserDataSharingConsentAudit.NOT_SET, [], []),
        (True, EnterpriseCustomer.DATA_CONSENT_OPTIONAL, UserDataSharingConsentAudit.ENABLED, [], []),
        (True, EnterpriseCustomer.DATA_CONSENT_OPTIONAL, UserDataSharingConsentAudit.DISABLED, [], []),
        (True, EnterpriseCustomer.DATA_CONSENT_OPTIONAL, UserDataSharingConsentAudit.NOT_SET, [], []),
    )
    @ddt.unpack
    def test_entitlements(
            self, enable_data_sharing_consent, enforce_data_sharing_consent,
            learner_consent_state, entitlements, expected_entitlements,
    ):
        """
        Test that entitlement property on `EnterpriseCustomerUser` returns correct data.

        This test verifies that entitlements returned by entitlement property on `EnterpriseCustomerUser
        has the expected behavior as listed down.
            1. Empty entitlements list if enterprise customer requires data sharing consent
                (this includes enforcing data sharing consent at login and at enrollment) and enterprise learner
                 does not consent to share data.
            2. Full list of entitlements for all other cases.

        Arguments:
            enable_data_sharing_consent (bool): True if enterprise customer enables data sharing consent,
                False it does not.
            enforce_data_sharing_consent (str): string for the location at which enterprise customer enforces
                data sharing consent, possible values are 'at_login', 'at_enrollment' and 'optional'.
            learner_consent_state (str): string containing the state of learner consent on data sharing,
                possible values are 'not_set', 'enabled' and 'disabled'.
            entitlements (list): A list of integers pointing to voucher ids generated in E-Commerce CAT tool.
            expected_entitlements (list): A list of integers pointing to voucher ids expected to be
                returned by the model.
        """
        user_id = 1
        enterprise_customer = EnterpriseCustomerFactory(
            enable_data_sharing_consent=enable_data_sharing_consent,
            enforce_data_sharing_consent=enforce_data_sharing_consent,
        )
        UserDataSharingConsentAuditFactory(
            user__id=user_id,
            user__enterprise_customer=enterprise_customer,
            state=learner_consent_state,
        )
        for entitlement in entitlements:
            EnterpriseCustomerEntitlementFactory(
                enterprise_customer=enterprise_customer,
                entitlement_id=entitlement,
            )

        enterprise_customer_user = EnterpriseCustomerUser.objects.get(id=user_id)
        assert sorted(enterprise_customer_user.entitlements) == sorted(expected_entitlements)


@mark.django_db
@ddt.ddt
class TestPendingEnterpriseCustomerUser(unittest.TestCase):
    """
    Tests of the PendingEnterpriseCustomerUser model.
    """

    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test ``EnterpriseCustomerUser`` conversion to string.
        """
        customer_user_id, user_email = 15, "some_email@example.com"
        customer_user = PendingEnterpriseCustomerUserFactory(id=customer_user_id, user_email=user_email)
        expected_to_str = "<PendingEnterpriseCustomerUser {ID}>: {enterprise_name} - {user_email}".format(
            ID=customer_user_id,
            enterprise_name=customer_user.enterprise_customer.name,
            user_email=user_email
        )
        self.assertEqual(method(customer_user), expected_to_str)


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomerBrandingConfiguration(unittest.TestCase):
    """
    Tests of the EnterpriseCustomerBrandingConfiguration model.
    """

    @staticmethod
    def _make_file_mock(name="logo.png", size=240*1024):
        """
        Build file mock.
        """
        file_mock = mock.MagicMock(spec=File, name="FileMock")
        file_mock.name = name
        file_mock.size = size
        return file_mock

    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test ``EnterpriseCustomerUser`` conversion to string.
        """
        file_mock = self._make_file_mock()
        customer_branding_config = EnterpriseCustomerBrandingConfiguration(
            id=1, logo=file_mock, enterprise_customer=EnterpriseCustomerFactory()
        )
        expected_str = "<EnterpriseCustomerBrandingConfiguration {ID}>: {enterprise_name}".format(
            ID=customer_branding_config.id,
            enterprise_name=customer_branding_config.enterprise_customer.name,
        )
        self.assertEqual(method(customer_branding_config), expected_str)

    def test_logo_path(self):
        """
        Test path of image file should be enterprise/branding/<model.id>/<model_id>_logo.<ext>.lower().
        """
        file_mock = self._make_file_mock()
        branding_config = EnterpriseCustomerBrandingConfiguration(
            id=1,
            enterprise_customer=EnterpriseCustomerFactory(),
            logo=file_mock
        )

        storage_mock = mock.MagicMock(spec=Storage, name="StorageMock")
        with mock.patch("django.core.files.storage.default_storage._wrapped", storage_mock):
            path = logo_path(branding_config, branding_config.logo.name)
            self.assertEqual(path, "enterprise/branding/1/1_logo.png")

    def test_branding_configuration_saving_successfully(self):
        """
        Test enterprise customer branding configuration saving successfully.
        """
        storage_mock = mock.MagicMock(spec=Storage, name="StorageMock")
        branding_config_1 = EnterpriseCustomerBrandingConfiguration(
            enterprise_customer=EnterpriseCustomerFactory(),
            logo="test1.png"
        )

        storage_mock.exists.return_value = True
        with mock.patch("django.core.files.storage.default_storage._wrapped", storage_mock):
            branding_config_1.save()
            self.assertEqual(EnterpriseCustomerBrandingConfiguration.objects.count(), 1)

        branding_config_2 = EnterpriseCustomerBrandingConfiguration(
            enterprise_customer=EnterpriseCustomerFactory(),
            logo="test2.png"
        )

        storage_mock.exists.return_value = False
        with mock.patch("django.core.files.storage.default_storage._wrapped", storage_mock):
            branding_config_2.save()
            self.assertEqual(EnterpriseCustomerBrandingConfiguration.objects.count(), 2)

    @ddt.data(
        (False, 350 * 1024),
        (False, 251 * 1024),
        (False, 250 * 1024),
        (False, 4 * 1024),
        (True, 2 * 1024),
        (True, 3 * 1024),
    )
    @ddt.unpack
    def test_image_size(self, valid_image, image_size):
        """
        Test image size, image_size < (4 * 1024) e.g. 4kb. See apps.py.
        """
        file_mock = mock.MagicMock(spec=File, name="FileMock")
        file_mock.name = "test1.png"
        file_mock.size = image_size
        branding_configuration = EnterpriseCustomerBrandingConfiguration(
            enterprise_customer=EnterpriseCustomerFactory(),
            logo=file_mock
        )

        if not valid_image:
            with self.assertRaises(ValidationError):
                branding_configuration.full_clean()
        else:
            branding_configuration.full_clean()  # exception here will fail the test

    @ddt.data(
        (False, ".jpg"),
        (False, ".gif"),
        (False, ".bmp"),
        (True, ".png"),
    )
    @ddt.unpack
    def test_image_type(self, valid_image, image_extension):
        """
        Test image type, currently .png is supported in configuration. see apps.py.
        """
        file_mock = mock.MagicMock(spec=File, name="FileMock")
        file_mock.name = "test1" + image_extension
        file_mock.size = 2 * 1024
        branding_configuration = EnterpriseCustomerBrandingConfiguration(
            enterprise_customer=EnterpriseCustomerFactory(),
            logo=file_mock
        )

        if not valid_image:
            with self.assertRaises(ValidationError):
                branding_configuration.full_clean()
        else:
            branding_configuration.full_clean()  # exception here will fail the test


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomerIdentityProvider(unittest.TestCase):
    """
    Tests of the EnterpriseCustomerIdentityProvider model.
    """

    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test ``EnterpriseCustomerIdentityProvider`` conversion to string.
        """
        provider_id, enterprise_customer_name = "saml-test", "TestShib"
        enterprise_customer = EnterpriseCustomerFactory(name=enterprise_customer_name)
        ec_idp = EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=enterprise_customer,
            provider_id=provider_id,
        )

        expected_to_str = "<EnterpriseCustomerIdentityProvider {provider_id}>: {enterprise_name}".format(
            provider_id=provider_id,
            enterprise_name=enterprise_customer_name,
        )
        self.assertEqual(method(ec_idp), expected_to_str)

    @mock.patch("enterprise.models.utils.get_identity_provider")
    def test_provider_name(self, mock_method):
        """
        Test provider_name property returns correct value without errors..
        """
        faker = FakerFactory.create()
        provider_name = faker.name()
        mock_method.return_value.configure_mock(name=provider_name)
        ec_idp = EnterpriseCustomerIdentityProviderFactory()

        assert ec_idp.provider_name == provider_name  # pylint: disable=no-member


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomerEntitlements(unittest.TestCase):
    """
    Tests of the TestEnterpriseCustomerEntitlements model.
    """
    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test ``TestEnterpriseCustomerEntitlements`` conversion to string.
        """
        entitlement_id, enterprise_customer_name = 1234, "TestShib"
        enterprise_customer = EnterpriseCustomerFactory(name=enterprise_customer_name)
        ec_entitlements = EnterpriseCustomerEntitlement(
            enterprise_customer=enterprise_customer,
            entitlement_id=entitlement_id,
        )

        expected_to_str = "<EnterpriseCustomerEntitlement {customer}: {id}>".format(
            customer=enterprise_customer,
            id=entitlement_id,
        )
        self.assertEqual(method(ec_entitlements), expected_to_str)


@mark.django_db
@ddt.ddt
class TestEnrollmentNotificationEmailTemplate(unittest.TestCase):
    """
    Tests of the EnrollmentNotificationEmailTemplate model.
    """

    def setUp(self):
        self.template = EnrollmentNotificationEmailTemplate.objects.create(
            site=Site.objects.get(id=1),
            plaintext_template=(
                'This is a template - testing {{ course_name }}, {{ other_value }}'
            ),
            html_template=(
                '<b>This is an HTML template! {{ course_name }}!!!</b>'
            ),
        )
        super(TestEnrollmentNotificationEmailTemplate, self).setUp()

    def test_render_all_templates(self):
        plain, html = self.template.render_all_templates(
            {
                "course_name": "real course",
                "other_value": "filled in",
            }
        )
        assert plain == 'This is a template - testing real course, filled in'
        assert html == '<b>This is an HTML template! real course!!!</b>'

    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test conversion to string.
        """
        expected_str = '<EnrollmentNotificationEmailTemplate for site with ID 1>'
        assert expected_str == method(self.template)


@mark.django_db
@ddt.ddt
class TestEnterpriseIntegratedChannel(unittest.TestCase):
    """
    Tests of the EnterpriseIntegratedChannel model.
    """
    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test ``EnterpriseIntegratedChannel`` conversion to string
        """
        channel = EnterpriseIntegratedChannel(
            id=1, name='CorporateLMS', data_type='course'
        )
        expected_to_str = "<EnterpriseIntegratedChannel CorporateLMS for course data with id 1>"
        assert expected_to_str == method(channel)


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomerPluginConfiguration(unittest.TestCase):
    """
    Tests of the EnterpriseCustomerPluginConfiguration model.
    """
    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test ``EnterpriseCustomerPluginConfiguration`` conversion to string
        """
        channel = EnterpriseIntegratedChannel(
            id=1, name='CorporateLMS', data_type='course'
        )
        faker = FakerFactory.create()
        customer_uuid = faker.uuid4()
        plugin_config = EnterpriseCustomerPluginConfiguration(
            enterprise_customer_uuid=customer_uuid, enterprise_integrated_channel=channel, active=False
        )
        expected_to_str = "<EnterpriseCustomerPluginConfiguration for enterprise {uuid} using channel CorporateLMS>"\
            .format(uuid=customer_uuid)
        assert expected_to_str == method(plugin_config)


@mark.django_db
@ddt.ddt
class TestCatalogTransmissionAudit(unittest.TestCase):
    """
    Tests of the CatalogTransmissionAudit model.
    """
    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test ``CatalogTransmissionAudit`` conversion to string
        """
        faker = FakerFactory.create()
        customer_uuid = faker.uuid4()
        course_audit = CatalogTransmissionAudit(
            id=1, enterprise_customer_uuid=customer_uuid, total_courses=50, status='success', error_message=None
        )
        expected_to_str = "<CatalogTransmissionAudit 1 for Enterprise {}> for 50 courses>".format(
            customer_uuid
        )
        assert expected_to_str == method(course_audit)


@mark.django_db
@ddt.ddt
class TestLearnerDataTransmissionAudit(unittest.TestCase):
    """
    Tests of the LearnerDataTransmissionAudit model.
    """
    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test ``LearnerDataTransmissionAudit`` conversion to string
        """
        learner_audit = LearnerDataTransmissionAudit(
            id=1,
            enterprise_course_enrollment_id=5,
            sapsf_user_id='sap_user',
            course_id='course-v1:edX+DemoX+DemoCourse',
            course_completed=True,
            completed_timestamp=1486755998,
            instructor_name='Professor Professorson',
            grade='Pass',
            error_message=None
        )
        expected_to_str = "<LearnerDataTransmissionAudit 1 for enterprise enrollment 5, SAP user sap_user," \
                          " and course course-v1:edX+DemoX+DemoCourse>"
        assert expected_to_str == method(learner_audit)


@mark.django_db
@ddt.ddt
class TestSAPSuccessFactorsEnterpriseCustomerConfiguration(unittest.TestCase):
    """
    Tests of the SAPSuccessFactorsEnterpriseCustomerConfiguration model.
    """
    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test ``SAPSuccessFactorsEnterpriseCustomerConfiguration`` conversion to string
        """
        faker = FakerFactory.create()
        customer_uuid = faker.uuid4()
        config = SAPSuccessFactorsEnterpriseCustomerConfiguration(
            enterprise_customer_uuid=customer_uuid,
            sapsf_base_url='enterprise.successfactors.com',
            key='key',
            secret='secret'
        )
        expected_to_str = "<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise {}>".format(
            customer_uuid
        )
        assert expected_to_str == method(config)


@mark.django_db
@ddt.ddt
class TestSAPSuccessFactorsGlobalConfiguration(unittest.TestCase):
    """
    Tests of the SAPSuccessFactorsGlobalConfiguration model.
    """
    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test ``SAPSuccessFactorsGlobalConfiguration`` conversion to string
        """
        config = SAPSuccessFactorsGlobalConfiguration(
            id=2,
            completion_status_api_path='completion_status',
            course_api_path='courses',
            oauth_api_path='oauth'
        )
        expected_to_str = "<SAPSuccessFactorsGlobalConfiguration with id 2>"
        assert expected_to_str == method(config)
