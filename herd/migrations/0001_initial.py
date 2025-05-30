# Generated by Django 5.2 on 2025-04-29 09:50

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Video',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('source_file', models.FileField(upload_to='uploads/%Y/%m/%d')),
                ('processed_file', models.FileField(upload_to='processed/%Y/%m/%d')),
                ('status', models.CharField(choices=[('uploaded', 'Uploaded'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed')], default='uploaded', max_length=20)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Detection',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('timestamp', models.FloatField()),
                ('confidence', models.FloatField()),
                ('frame', models.IntegerField()),
                ('x', models.FloatField()),
                ('y', models.FloatField()),
                ('width', models.FloatField()),
                ('height', models.FloatField()),
                ('video', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detections', to='herd.video')),
            ],
            options={
                'indexes': [models.Index(fields=['video', 'timestamp'], name='herd_detect_video_i_d704c2_idx')],
            },
        ),
    ]
