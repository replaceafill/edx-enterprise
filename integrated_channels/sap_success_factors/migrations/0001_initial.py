# -*- coding: utf-8 -*-
# Generated by Django 1.9.12 on 2017-02-13 11:14
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CatalogTransmissionAudit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start', models.DateTimeField(blank=True, null=True, verbose_name='start')),
                ('end', models.DateTimeField(blank=True, null=True, verbose_name='end')),
                ('enterprise_customer_uuid', models.UUIDField()),
                ('total_courses', models.PositiveIntegerField()),
                ('status', models.CharField(max_length=100)),
                ('error_message', models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='LearnerDataTransmissionAudit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enterprise_course_enrollment_id', models.PositiveIntegerField()),
                ('sapsf_user_id', models.CharField(max_length=255)),
                ('course_id', models.CharField(max_length=255)),
                ('course_completed', models.BooleanField(default=True)),
                ('completed_timestamp', models.BigIntegerField()),
                ('instructor_name', models.CharField(blank=True, max_length=255)),
                ('grade', models.CharField(max_length=100)),
                ('status', models.CharField(max_length=100)),
                ('error_message', models.TextField(blank=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='SAPSuccessFactorsEnterpriseCustomerConfiguration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('change_date', models.DateTimeField(auto_now_add=True, verbose_name='Change date')),
                ('enabled', models.BooleanField(default=False, verbose_name='Enabled')),
                ('enterprise_customer_uuid', models.UUIDField(unique=True)),
                ('sapsf_base_url', models.CharField(max_length=255)),
                ('key', models.CharField(blank=True, max_length=255, verbose_name='Client ID')),
                ('secret', models.CharField(blank=True, max_length=255, verbose_name='Client Secret')),
                ('changed_by', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, verbose_name='Changed by')),
            ],
        ),
        migrations.CreateModel(
            name='SAPSuccessFactorsGlobalConfiguration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('change_date', models.DateTimeField(auto_now_add=True, verbose_name='Change date')),
                ('enabled', models.BooleanField(default=False, verbose_name='Enabled')),
                ('completion_status_api_path', models.CharField(max_length=255)),
                ('course_api_path', models.CharField(max_length=255)),
                ('oauth_api_path', models.CharField(max_length=255)),
                ('provider_id', models.CharField(default='EDX', max_length=100)),
                ('changed_by', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, verbose_name='Changed by')),
            ],
        ),
    ]
