# Generated by Django 2.0.2 on 2018-09-06 14:34

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('data_refinery_common', '0016_auto_20180824_1717'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='sample',
            name='is_downloaded',
        ),
        migrations.RemoveField(
            model_name='surveyjob',
            name='replication_ended_at',
        ),
        migrations.RemoveField(
            model_name='surveyjob',
            name='replication_started_at',
        ),
    ]
