# Generated by Django 3.2.10 on 2024-01-21 14:14

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_useraccountportfolio_balance'),
        ('markets', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='stockbalance',
            name='is_buy_position',
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transaction_type', models.CharField(choices=[('BUY', 'Buy'), ('SELL', 'Sell')], max_length=4)),
                ('symbol', models.CharField(max_length=30)),
                ('quantity', models.IntegerField()),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('user_profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='accounts.useraccountportfolio')),
            ],
        ),
    ]